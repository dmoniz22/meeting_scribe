#!/usr/bin/env python3
"""
server.py - Audio Daemon HTTP Server for MeetScribe

Provides HTTP endpoints for controlling audio recording:
- POST /start - Begin recording a meeting
- POST /stop - Stop recording
- GET /status - Get current recording status and audio levels

The server runs on a Unix socket for security and communicates with the
main API server.
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
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import UnixStreamServer
import socket


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
        recordings_path: str = "/data/recordings",
        socket_path: str = "/tmp/meetscribe-audio.sock",
        redis_host: str = "localhost",
        redis_port: int = 6379,
    ):
        self.recordings_path = Path(recordings_path)
        self.socket_path = socket_path
        self.redis_host = redis_host
        self.redis_port = redis_port

        self.state = RecordingState()
        self.capture: Optional[AudioCapture] = None
        self.device_monitor: Optional[DeviceMonitor] = None

        # Ensure recordings directory exists
        self.recordings_path.mkdir(parents=True, exist_ok=True)

        # Redis connection (optional)
        self.redis_client = None
        self._init_redis()

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

            # Set up audio routing automatically
            setup_recording_routing()

            # Create capture instance
            self.capture = AudioCapture(
                meeting_id=meeting_id,
                output_dir=str(self.recordings_path),
                config=AudioConfig(),
                level_callback=self._publish_levels,
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

            # Clean up audio routing
            cleanup_routing()

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


class UnixHTTPServer(UnixStreamServer):
    """HTTP server that listens on a Unix socket."""

    def server_bind(self):
        # Remove existing socket file or directory
        if os.path.exists(self.server_address):
            if os.path.isdir(self.server_address):
                import shutil

                shutil.rmtree(self.server_address)
            else:
                os.unlink(self.server_address)
        super().server_bind()
        # Set permissions
        os.chmod(self.server_address, 0o666)


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
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

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

        else:
            self._send_json({"error": "Not found"}, 404)


def run_server(
    socket_path: str = "/tmp/meetscribe-audio.sock", recordings_path: str = None
):
    """Run the audio daemon server."""
    print("=" * 60)
    print("MeetScribe Audio Daemon")
    print("=" * 60)

    # Use default path relative to script if not provided
    if recordings_path is None:
        recordings_path = str(Path(__file__).parent.parent / "data" / "recordings")

    # Create daemon instance
    daemon = AudioDaemon(socket_path=socket_path, recordings_path=recordings_path)

    # Make daemon accessible to request handler
    RequestHandler.daemon = daemon

    # Start device monitor
    print("\nStarting device monitor...")
    daemon.device_monitor = DeviceMonitor()
    daemon.device_monitor.start()

    # Create and start server
    print(f"\nStarting HTTP server on Unix socket: {socket_path}")
    server = UnixHTTPServer(socket_path, RequestHandler)

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
    print(f"  Socket: {socket_path}")
    print(f"  Recordings: {recordings_path}")
    print("\nPress Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except Exception as e:
        print(f"Server error: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MeetScribe Audio Daemon")
    parser.add_argument(
        "--socket",
        default="/tmp/meetscribe-audio.sock",
        help="Unix socket path (default: /tmp/meetscribe-audio.sock)",
    )
    parser.add_argument(
        "--recordings",
        default=None,
        help="Recordings directory (default: ../data/recordings)",
    )
    args = parser.parse_args()

    run_server(socket_path=args.socket, recordings_path=args.recordings)
