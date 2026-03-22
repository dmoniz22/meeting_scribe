#!/usr/bin/env python3
"""
capture_parec.py - Audio capture module for MeetScribe using PulseAudio parec
Captures audio from PipeWire virtual source using parec command.

Usage:
    from capture_parec import AudioCapture
    capture = AudioCapture(meeting_id="uuid", output_dir="/path/to/recordings")
    capture.start()
    # ... recording ...
    capture.stop()
"""

import wave
import time
import os
import signal
import sys
import subprocess
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
import threading
import queue

import numpy as np
from scipy import signal as scipy_signal


@dataclass
class AudioConfig:
    """Configuration for audio capture."""

    target_sample_rate: int = 16000  # Output rate (Whisper's native rate)
    capture_sample_rate: int = 44100  # Matches virtual audio device (meetscribe_sink)
    channels: int = 2  # Use 1 for mono microphones
    dtype: str = "float32"
    chunk_duration: int = 30  # seconds per WAV file

    # Microphone source (use "default" for system default)
    mic_device: str = "easyeffects_source"

    # System audio source (headphone monitor - captures what you hear)
    # Example: "alsa_output.usb-Logitech_Logi_USB_Headset_000000000000-00.iec958-stereo.monitor"
    system_device: str = ""

    # Legacy compatibility
    @property
    def device(self) -> str:
        return self.mic_device


class AudioCapture:
    """
    Captures audio from a PipeWire virtual source using parec and writes to WAV files.

    Features:
    - Records in configurable chunks (default 30 seconds)
    - Calculates RMS audio levels in real-time
    - Thread-safe start/stop
    - Automatic file naming with timestamps
    - Uses parec to capture from PipeWire virtual devices
    """

    def __init__(
        self,
        meeting_id: str,
        output_dir: str,
        config: Optional[AudioConfig] = None,
        level_callback: Optional[Callable[[float, float], None]] = None,
    ):
        self.meeting_id = meeting_id
        self.output_dir = Path(output_dir) / meeting_id
        self.config = config or AudioConfig()
        self.level_callback = level_callback

        # Recording state
        self.is_recording = False
        self.parec_process: Optional[subprocess.Popen] = None
        self.capture_thread: Optional[threading.Thread] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.audio_queue: queue.Queue = queue.Queue(maxsize=100)  # Bounded queue

        # File management
        self.current_chunk: int = 0
        self.current_file: Optional[wave.Wave_write] = None
        self.chunk_start_time: Optional[datetime] = None
        self.frames_written: int = 0

        # Level monitoring
        self.current_levels = {"system": 0.0, "mic": 0.0}

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Audio format settings
        self.sample_width = 2  # 16-bit

    def _calculate_rms(self, audio_data: np.ndarray) -> tuple[float, float]:
        """Calculate RMS levels for left (system) and right (mic) channels."""
        if audio_data.size == 0:
            return 0.0, 0.0

        # Split channels (stereo: left = system audio, right = mic)
        left_channel = audio_data[:, 0] if audio_data.ndim > 1 else audio_data
        right_channel = (
            audio_data[:, 1]
            if audio_data.ndim > 1 and audio_data.shape[1] > 1
            else audio_data
        )

        # Calculate RMS (Root Mean Square)
        rms_left = np.sqrt(np.mean(left_channel**2))
        rms_right = np.sqrt(np.mean(right_channel**2))

        return float(rms_left), float(rms_right)

    def _capture_worker(self):
        """Background thread that reads from ffmpeg and writes to a named pipe."""
        import tempfile
        import os

        # Create a named pipe for ffmpeg output
        self.fifo_path = f"/tmp/meetscribe_fifo_{self.meeting_id}"
        os.mkfifo(self.fifo_path)

        # Build ffmpeg command using PulseAudio
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-f",
            "pulse",
            "-i",
            self.config.device,
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(self.config.capture_sample_rate),
            "-ac",
            str(self.config.channels),
            self.fifo_path,
        ]

        print(f"Starting ffmpeg: {' '.join(cmd)}")

        try:
            self.parec_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,  # Unbuffered
            )

            # Open the pipe for reading
            fifo = open(self.fifo_path, "rb")

            # Read raw PCM data in chunks
            frame_size = (
                self.config.channels * self.sample_width
            )  # 4 bytes for stereo 16-bit
            chunk_bytes = 1024 * frame_size

            while self.is_recording and self.parec_process.poll() is None:
                try:
                    raw_data = fifo.read(chunk_bytes)

                    if not raw_data:
                        time.sleep(0.001)
                        continue

                    # Convert bytes to numpy array (int16 -> float32)
                    # struct.unpack gives signed short (int16)
                    num_frames = len(raw_data) // frame_size
                    num_samples = len(raw_data) // self.sample_width

                    # Unpack as int16, reshape to (frames, channels)
                    fmt = f"{num_samples}h"  # 'h' = signed short (int16)
                    samples = struct.unpack(
                        fmt, raw_data[: num_samples * self.sample_width]
                    )
                    audio_int16 = np.array(samples, dtype=np.int16)

                    # Reshape to (frames, channels)
                    if self.config.channels > 1:
                        audio_int16 = audio_int16.reshape(-1, self.config.channels)

                    # Convert to float32 normalized [-1, 1]
                    audio_float32 = audio_int16.astype(np.float32) / 32768.0

                    # Calculate levels
                    system_level, mic_level = self._calculate_rms(audio_float32)
                    self.current_levels = {"system": system_level, "mic": mic_level}

                    # Call level callback if provided
                    if self.level_callback:
                        self.level_callback(system_level, mic_level)

                    # Put in queue (block if full)
                    try:
                        self.audio_queue.put(audio_float32, timeout=1.0)
                    except queue.Full:
                        print("Warning: Audio queue full, dropping frame")

                except Exception as e:
                    if self.is_recording:
                        print(f"Error reading audio: {e}")
                    break

        except Exception as e:
            print(f"Error starting ffmpeg: {e}")
        finally:
            if self.parec_process:
                self.parec_process.terminate()
                try:
                    self.parec_process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.parec_process.kill()
                self.parec_process = None
            # Cleanup FIFO
            if hasattr(self, "fifo_path") and os.path.exists(self.fifo_path):
                os.unlink(self.fifo_path)

    def _writer_worker(self):
        """Background thread that writes audio chunks to WAV files."""
        while self.is_recording or not self.audio_queue.empty():
            try:
                # Get audio data with timeout
                audio_data = self.audio_queue.get(timeout=1.0)

                # Check if we need to start a new chunk
                if self.current_file is None or self._should_rotate_chunk():
                    self._start_new_chunk()

                # Write audio data
                if self.current_file:
                    # Convert float32 to int16 for WAV
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                    self.current_file.writeframes(audio_int16.tobytes())
                    self.frames_written += len(audio_data)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in writer worker: {e}")

    def _should_rotate_chunk(self) -> bool:
        """Check if we should start a new chunk file."""
        if not self.chunk_start_time:
            return True

        elapsed = (datetime.now() - self.chunk_start_time).total_seconds()
        return elapsed >= self.config.chunk_duration

    def _start_new_chunk(self):
        """Close current chunk file and start a new one."""
        # Close existing file
        if self.current_file:
            self.current_file.close()
            print(f"Closed chunk {self.current_chunk:03d}")

        # Create new file
        chunk_filename = self.output_dir / f"chunk_{self.current_chunk:03d}.wav"
        self.current_file = wave.open(str(chunk_filename), "wb")
        self.current_file.setnchannels(self.config.channels)
        self.current_file.setsampwidth(2)  # 16-bit
        self.current_file.setframerate(self.config.capture_sample_rate)

        self.chunk_start_time = datetime.now()
        self.frames_written = 0
        self.current_chunk += 1

        print(f"Started new chunk: {chunk_filename}")

    def start(self):
        """Start audio capture."""
        if self.is_recording:
            print("Already recording!")
            return

        # Check if parec is available
        try:
            subprocess.run(["parec", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("parec not found. Please install pulseaudio-utils")

        # Check if audio device exists
        try:
            result = subprocess.run(
                ["pactl", "list", "sources"], capture_output=True, text=True
            )
            if self.config.device not in result.stdout:
                print(f"⚠️ Warning: Audio device '{self.config.device}' not found!")
                print("Available sources:")
                for line in result.stdout.split("\n"):
                    if "Name:" in line:
                        print(f"  {line}")
                raise RuntimeError(
                    f"Audio device '{self.config.device}' not found. Run setup_pipewire.sh first."
                )
        except Exception as e:
            print(f"Error checking audio devices: {e}")

        print(f"Starting audio capture for meeting {self.meeting_id}")
        print(f"Output directory: {self.output_dir}")
        print(f"Source device: {self.config.device}")
        print(f"Sample rate: {self.config.capture_sample_rate} Hz")
        print(f"Channels: {self.config.channels}")

        self.is_recording = True
        self.current_chunk = 0

        # Start the threads
        self.capture_thread = threading.Thread(target=self._capture_worker)
        self.writer_thread = threading.Thread(target=self._writer_worker)
        self.capture_thread.start()
        self.writer_thread.start()

        print("✓ Audio capture started")

    def stop(self) -> Path:
        """Stop audio capture and return the output directory."""
        if not self.is_recording:
            print("Not recording!")
            return self.output_dir

        print("\nStopping audio capture...")
        self.is_recording = False

        # Terminate parec
        if self.parec_process:
            self.parec_process.terminate()
            try:
                self.parec_process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.parec_process.kill()
            self.parec_process = None

        # Wait for threads to finish
        if self.capture_thread:
            self.capture_thread.join(timeout=5.0)
        if self.writer_thread:
            self.writer_thread.join(timeout=5.0)

        # Close current file
        if self.current_file:
            self.current_file.close()
            self.current_file = None

        print("✓ Audio capture stopped")
        print(f"Recorded {self.current_chunk} chunk(s) to {self.output_dir}")

        return self.output_dir

    def get_current_levels(self) -> dict:
        """Get current audio levels."""
        return self.current_levels.copy()

    def concatenate_chunks(self, output_filename: str = "full_recording.wav") -> Path:
        """Concatenate all chunks into a single WAV file."""
        import subprocess

        output_path = self.output_dir / output_filename
        chunk_list = sorted(self.output_dir.glob("chunk_*.wav"))

        if not chunk_list:
            print("No chunks to concatenate")
            return output_path

        print(f"\nConcatenating {len(chunk_list)} chunks...")

        # Create a file list for ffmpeg
        list_file = self.output_dir / "chunks.txt"
        with open(list_file, "w") as f:
            for chunk in chunk_list:
                f.write(f"file '{chunk.name}'\n")

        # Use ffmpeg to concatenate
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file),
                    "-acodec",
                    "pcm_s16le",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                cwd=self.output_dir,
            )
            print(f"✓ Created {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error concatenating chunks: {e}")
        finally:
            # Clean up list file
            list_file.unlink(missing_ok=True)

        return output_path


# CLI for testing
if __name__ == "__main__":
    import argparse
    import uuid

    parser = argparse.ArgumentParser(description="Test audio capture with parec")
    parser.add_argument(
        "--duration", type=int, default=10, help="Recording duration in seconds"
    )
    parser.add_argument(
        "--output", type=str, default="/tmp/meetscribe_test", help="Output directory"
    )
    parser.add_argument(
        "--concatenate", action="store_true", help="Concatenate chunks after recording"
    )
    parser.add_argument(
        "--device", type=str, default="meetscribe_source", help="PulseAudio source name"
    )
    args = parser.parse_args()

    def print_levels(system, mic):
        """Print audio levels."""
        sys_bar = "█" * int(system * 50)
        mic_bar = "█" * int(mic * 50)
        print(f"\rSystem: [{sys_bar:<50}] Mic: [{mic_bar:<50}]", end="", flush=True)

    meeting_id = str(uuid.uuid4())
    config = AudioConfig(device=args.device)
    capture = AudioCapture(
        meeting_id=meeting_id,
        output_dir=args.output,
        config=config,
        level_callback=print_levels,
    )

    def signal_handler(sig, frame):
        print("\n\nInterrupted!")
        capture.stop()
        if args.concatenate:
            capture.concatenate_chunks()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(
        f"Recording from device '{args.device}' for {args.duration} seconds (Ctrl+C to stop early)..."
    )
    capture.start()

    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass

    print("\n")
    capture.stop()

    if args.concatenate:
        capture.concatenate_chunks()

    print(f"\nFiles saved to: {capture.output_dir}")
