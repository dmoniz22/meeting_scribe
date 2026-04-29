#!/usr/bin/env python3
"""
server_tcp.py - Audio Daemon HTTP Server for MeetScribe (TCP version)

Provides HTTP endpoints for controlling audio recording via TCP port:
- POST /start - Begin recording a meeting
- POST /stop - Stop recording
- GET /status - Get current recording status and audio levels
- GET /health - Health check

The server runs on TCP port 8082 for better Docker compatibility.
"""

import os
import sys
import json
import asyncio
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from capture import AudioCapture, AudioConfig
from device_monitor import DeviceMonitor
from audio_router import setup_recording_routing, cleanup_routing

# HTTP server imports
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import json


@dataclass
class RecordingState:
    """Current recording state."""

    is_recording: bool = False
    meeting_id: Optional[str] = None
    started_at: Optional[str] = None
    duration_seconds: float = 0.0
    chunks_recorded: int = 0
    system_level: float = 0.0
    mic_level: float = 0.0
    error: Optional[str] = None


class AudioDaemon:
    """
    Main Audio Daemon that manages recording and device monitoring.
    """

    def __init__(
        self,
        recordings_path: str = "/home/dmoniz/projects/meeting_transcriber/data/recordings",
        host: str = "0.0.0.0",
        port: int = 8082,
        redis_host: str = "localhost",
        redis_port: int = 6381,
        audio_config=None,
    ):
        self.recordings_path = Path(recordings_path)
        self.host = host
        self.port = port
        self.redis_host = redis_host
        self.redis_port = redis_port

        # Load persisted config or use provided/defaults
        self.config_file = Path(__file__).parent / "audio_config.json"
        persisted = self._load_config()
        if audio_config:
            self.audio_config = audio_config
        elif persisted:
            self.audio_config = AudioConfig(
                system_gain=persisted.get("system_gain", 0.5),
                mic_gain=persisted.get("mic_gain", 10.0),
            )
        else:
            self.audio_config = AudioConfig()

        self.state = RecordingState()
        self.capture: Optional[AudioCapture] = None
        self.device_monitor: Optional[DeviceMonitor] = None

        # Ensure recordings directory exists
        self.recordings_path.mkdir(parents=True, exist_ok=True)

        # Redis connection (optional)
        self.redis_client = None
        self._init_redis()

    def _load_config(self) -> Optional[dict]:
        """Load persisted audio config from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
        return None

    def _save_config(self):
        """Persist audio config to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(
                    {
                        "system_gain": self.audio_config.system_gain,
                        "mic_gain": self.audio_config.mic_gain,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"Warning: Could not save config file: {e}")

    def _init_redis(self):
        """Initialize Redis connection for publishing audio levels."""
        try:
            import redis

            self.redis_client = redis.Redis(
                host=self.redis_host, port=self.redis_port, decode_responses=True
            )
            self.redis_client.ping()
            print(f"✓ Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"⚠ Redis not available: {e}")
            self.redis_client = None

    def _publish_levels(self, system_level: float, mic_level: float):
        """Publish audio levels to Redis."""
        self.state.system_level = system_level
        self.state.mic_level = mic_level

        if self.redis_client and self.state.meeting_id:
            try:
                channel = f"audio:levels:{self.state.meeting_id}"
                data = json.dumps(
                    {
                        "rms_system": system_level,
                        "rms_mic": mic_level,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                self.redis_client.publish(channel, data)
            except Exception as e:
                print(f"Error publishing to Redis: {e}")

    def _set_mic_mute(self, mute: bool = True):
        """Mute or unmute the microphone.

        Args:
            mute: True to mute, False to unmute
        """
        import subprocess

        # Find the headset mic - try multiple sources
        mic_ids = ["84", "153"]  # Common IDs for Logi USB Headset Mono

        for mic_id in mic_ids:
            result = subprocess.run(
                ["wpctl", "set-mute", mic_id, "1" if mute else "0"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"  Mic {'muted' if mute else 'unmuted'} (ID: {mic_id})")
                return

        # If wpctl didn't work, try pactl
        result = subprocess.run(
            ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1" if mute else "0"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  Mic {'muted' if mute else 'unmuted'} (via pactl)")

    def start_recording(self, meeting_id: str) -> dict:
        """Start recording a meeting."""
        if self.state.is_recording:
            return {
                "success": False,
                "error": "Already recording",
                "meeting_id": self.state.meeting_id,
            }

        try:
            print(f"\n{'=' * 50}")
            print(f"Starting recording for meeting: {meeting_id}")
            print(f"{'=' * 50}")

            # Unmute microphone for recording
            self._set_mic_mute(False)
            print("  Microphone unmuted for recording")

            # Set up audio routing automatically
            try:
                setup_recording_routing()
            except Exception as e:
                print(f"Warning: Could not set up audio routing: {e}")

            # Create capture instance with configured devices
            self.capture = AudioCapture(
                meeting_id=meeting_id,
                output_dir=str(self.recordings_path),
                config=self.audio_config,
                level_callback=self._publish_levels,
                started_at=self.state.started_at,
            )

            # Start recording
            self.capture.start()

            # Update state
            self.state.is_recording = True
            self.state.meeting_id = meeting_id
            self.state.started_at = datetime.utcnow().isoformat()
            self.state.duration_seconds = 0.0
            self.state.chunks_recorded = 0
            self.state.error = None

            print(f"✓ Recording started successfully")

            return {
                "success": True,
                "meeting_id": meeting_id,
                "started_at": self.state.started_at,
            }

        except Exception as e:
            error_msg = str(e)
            print(f"✗ Error starting recording: {error_msg}")
            self.state.error = error_msg
            self.state.is_recording = False
            self.capture = None

            return {"success": False, "error": error_msg}

    def stop_recording(self) -> dict:
        """Stop the current recording."""
        if not self.state.is_recording:
            return {"success": False, "error": "Not recording"}

        try:
            print(f"\n{'=' * 50}")
            print(f"Stopping recording for meeting: {self.state.meeting_id}")
            print(f"{'=' * 50}")

            # Stop capture
            output_dir = self.capture.stop()

            # Mute microphone after recording stops
            self._set_mic_mute(True)
            print("  Microphone muted after recording")

            # Clean up audio routing
            try:
                cleanup_routing()
            except Exception as e:
                print(f"Warning: Could not clean up audio routing: {e}")

            # Concatenate chunks
            full_path = self.capture.concatenate_chunks()

            # Calculate duration
            if self.state.started_at:
                started = datetime.fromisoformat(self.state.started_at)
                duration = (datetime.utcnow() - started).total_seconds()
            else:
                duration = 0

            # Update state
            result = {
                "success": True,
                "meeting_id": self.state.meeting_id,
                "duration_seconds": duration,
                "chunks_recorded": self.capture.current_chunk,
                "audio_path": str(full_path),
                "output_dir": str(output_dir),
            }

            # Reset state
            self.state.is_recording = False
            self.state.meeting_id = None
            self.state.started_at = None
            self.state.duration_seconds = 0
            self.state.chunks_recorded = 0
            self.capture = None

            print(f"✓ Recording stopped successfully")
            print(f"  Duration: {duration:.1f} seconds")
            print(f"  Chunks: {result['chunks_recorded']}")
            print(f"  File: {result['audio_path']}")

            return result

        except Exception as e:
            error_msg = str(e)
            print(f"✗ Error stopping recording: {error_msg}")
            self.state.error = error_msg

            return {"success": False, "error": error_msg}

    def get_config(self) -> dict:
        """Get current audio configuration."""
        return {
            "system_gain": self.audio_config.system_gain,
            "mic_gain": self.audio_config.mic_gain,
        }

    def set_config(
        self, system_gain: Optional[float] = None, mic_gain: Optional[float] = None
    ) -> dict:
        """Update audio configuration (applied on next recording)."""
        if system_gain is not None:
            self.audio_config.system_gain = float(system_gain)
        if mic_gain is not None:
            self.audio_config.mic_gain = float(mic_gain)
        self._save_config()
        return self.get_config()

    def get_status(self) -> dict:
        """Get current recording status."""
        status = {
            "is_recording": self.state.is_recording,
            "meeting_id": self.state.meeting_id,
            "started_at": self.state.started_at,
        }

        if self.state.is_recording and self.state.started_at:
            started = datetime.fromisoformat(self.state.started_at)
            status["duration_seconds"] = (datetime.utcnow() - started).total_seconds()
            status["rms_system"] = self.state.system_level
            status["rms_mic"] = self.state.mic_level
            status["chunks_recorded"] = (
                self.capture.current_chunk if self.capture else 0
            )

        if self.state.error:
            status["error"] = self.state.error

        return status


class ReuseAddrHTTPServer(HTTPServer):
    """HTTP server that allows address reuse (for quick restarts)."""

    allow_reuse_address = True


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Audio Daemon."""

    daemon: Optional[AudioDaemon] = None

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_json(self) -> dict:
        """Read JSON from request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            return json.loads(body.decode())
        return {}

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/status":
            status = self.daemon.get_status()
            self._send_json(status)
        elif self.path == "/health":
            self._send_json(
                {
                    "status": "ok",
                    "daemon": "meetscribe-audio",
                    "recording": self.daemon.state.is_recording,
                }
            )
        elif self.path == "/config":
            config = self.daemon.get_config()
            self._send_json(config)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/start":
            data = self._read_json()
            meeting_id = data.get("meeting_id")

            if not meeting_id:
                self._send_json({"error": "meeting_id required"}, 400)
                return

            result = self.daemon.start_recording(meeting_id)
            self._send_json(result, 200 if result["success"] else 500)

        elif self.path == "/stop":
            result = self.daemon.stop_recording()
            self._send_json(result, 200 if result["success"] else 500)

        elif self.path == "/shutdown":
            self._send_json({"status": "shutting_down"})
            # Schedule shutdown
            import threading

            def shutdown():
                import time

                time.sleep(1)
                if self.daemon.state.is_recording:
                    self.daemon.stop_recording()
                if self.daemon.device_monitor:
                    self.daemon.device_monitor.stop()
                self.server_close()
                raise SystemExit(0)

            threading.Thread(target=shutdown, daemon=True).start()

        elif self.path == "/config":
            data = self._read_json()
            config = self.daemon.set_config(
                system_gain=data.get("system_gain"),
                mic_gain=data.get("mic_gain"),
            )
            self._send_json(config)

        elif self.path == "/restart":
            # Restart audio routing (useful if routing gets broken)
            result = {"success": True, "message": "Audio routing restarted"}
            try:
                # Stop any current recording
                if self.daemon.state.is_recording:
                    self.daemon.stop_recording()
                    result["was_recording"] = True

                # Clean up old routing
                cleanup_routing()

                # Re-setup routing
                setup_recording_routing()

                result["message"] = "Audio routing reconfigured successfully"
                print("✓ Audio routing restarted")
            except Exception as e:
                result["success"] = False
                result["error"] = str(e)
                result["message"] = f"Failed to restart routing: {e}"
                print(f"✗ Error restarting audio routing: {e}")

            self._send_json(result)

        else:
            self._send_json({"error": "Not found"}, 404)


def run_server(
    host: str = "0.0.0.0",
    port: int = 9000,
    recordings_path: str = None,
    audio_config=None,
):
    """Run the audio daemon server on TCP."""
    print("=" * 60)
    print("MeetScribe Audio Daemon (TCP Mode)")
    print("=" * 60)

    # Use default path relative to script if not provided
    if recordings_path is None:
        recordings_path = str(Path(__file__).parent.parent / "data" / "recordings")

    # Create daemon instance
    daemon = AudioDaemon(
        host=host, port=port, recordings_path=recordings_path, audio_config=audio_config
    )

    # Make daemon accessible to request handler
    RequestHandler.daemon = daemon

    # Start device monitor
    print("\nStarting device monitor...")
    daemon.device_monitor = DeviceMonitor()
    daemon.device_monitor.start()

    # Create and start server
    print(f"\nStarting HTTP server on TCP: {host}:{port}")
    server = ReuseAddrHTTPServer((host, port), RequestHandler)

    def signal_handler(sig, frame):
        print("\n\nShutting down...")
        if daemon.state.is_recording:
            daemon.stop_recording()
        daemon.device_monitor.stop()
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("✓ Audio daemon ready")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Recordings: {recordings_path}")
    print(f"  Health: http://{host}:{port}/health")
    print("\nPress Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except Exception as e:
        print(f"Server error: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MeetScribe Audio Daemon (TCP)")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=9000, help="Port to listen on (default: 9000)"
    )
    parser.add_argument(
        "--recordings",
        default=None,
        help="Recordings directory (default: ../data/recordings)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Comma-separated list of audio devices to try (in priority order)",
    )
    parser.add_argument(
        "--mono",
        action="store_true",
        help="Use mono mode for microphone (for mono headsets)",
    )
    args = parser.parse_args()

    # AudioConfig uses dual-stream capture (no channels/device_names params needed)
    audio_config = AudioConfig()

    run_server(
        host=args.host,
        port=args.port,
        recordings_path=args.recordings,
        audio_config=audio_config,
    )
