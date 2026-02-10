#!/usr/bin/env python3
"""
capture.py - Audio capture module for MeetScribe
Captures audio from PipeWire virtual source and writes WAV chunks.

Usage:
    from capture import AudioCapture
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
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
import threading
import queue

import numpy as np
import sounddevice as sd


@dataclass
class AudioConfig:
    """Configuration for audio capture."""
    sample_rate: int = 16000
    channels: int = 2
    dtype: str = "float32"
    chunk_duration: int = 30  # seconds per WAV file
    device: str = "meetscribe_source"


class AudioCapture:
    """
    Captures audio from a PipeWire virtual source and writes to WAV files.
    
    Features:
    - Records in configurable chunks (default 30 seconds)
    - Calculates RMS audio levels in real-time
    - Thread-safe start/stop
    - Automatic file naming with timestamps
    """
    
    def __init__(
        self,
        meeting_id: str,
        output_dir: str,
        config: Optional[AudioConfig] = None,
        level_callback: Optional[Callable[[float, float], None]] = None
    ):
        self.meeting_id = meeting_id
        self.output_dir = Path(output_dir) / meeting_id
        self.config = config or AudioConfig()
        self.level_callback = level_callback
        
        # Recording state
        self.is_recording = False
        self.stream: Optional[sd.InputStream] = None
        self.audio_queue: queue.Queue = queue.Queue()
        self.writer_thread: Optional[threading.Thread] = None
        self.level_thread: Optional[threading.Thread] = None
        
        # File management
        self.current_chunk: int = 0
        self.current_file: Optional[wave.Wave_write] = None
        self.chunk_start_time: Optional[datetime] = None
        self.frames_written: int = 0
        
        # Level monitoring
        self.current_levels = {"system": 0.0, "mic": 0.0}
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find the audio device
        self.device_id = self._find_device()
        
    def _find_device(self) -> int:
        """Find the MeetScribe virtual source device."""
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if self.config.device in device.get("name", "").lower():
                print(f"Found device: {device['name']} (id: {i})")
                return i
        
        # Fallback to default input
        print(f"Warning: Device '{self.config.device}' not found, using default input")
        return sd.default.device[0]
    
    def _calculate_rms(self, audio_data: np.ndarray) -> tuple[float, float]:
        """Calculate RMS levels for left (system) and right (mic) channels."""
        if audio_data.size == 0:
            return 0.0, 0.0
        
        # Split channels (stereo: left = system audio, right = mic)
        left_channel = audio_data[:, 0] if audio_data.ndim > 1 else audio_data
        right_channel = audio_data[:, 1] if audio_data.ndim > 1 and audio_data.shape[1] > 1 else audio_data
        
        # Calculate RMS (Root Mean Square)
        rms_left = np.sqrt(np.mean(left_channel ** 2))
        rms_right = np.sqrt(np.mean(right_channel ** 2))
        
        return float(rms_left), float(rms_right)
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags):
        """Called by sounddevice for each audio buffer."""
        if status:
            print(f"Audio callback status: {status}")
        
        if self.is_recording:
            # Put audio data in queue for file writer
            self.audio_queue.put(indata.copy())
            
            # Calculate levels
            system_level, mic_level = self._calculate_rms(indata)
            self.current_levels = {"system": system_level, "mic": mic_level}
            
            # Call level callback if provided
            if self.level_callback:
                self.level_callback(system_level, mic_level)
    
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
        self.current_file.setframerate(self.config.sample_rate)
        
        self.chunk_start_time = datetime.now()
        self.frames_written = 0
        self.current_chunk += 1
        
        print(f"Started new chunk: {chunk_filename}")
    
    def start(self):
        """Start audio capture."""
        if self.is_recording:
            print("Already recording!")
            return
        
        print(f"Starting audio capture for meeting {self.meeting_id}")
        print(f"Output directory: {self.output_dir}")
        print(f"Device: {self.device_id}")
        print(f"Sample rate: {self.config.sample_rate} Hz")
        print(f"Channels: {self.config.channels}")
        
        self.is_recording = True
        self.current_chunk = 0
        
        # Start the writer thread
        self.writer_thread = threading.Thread(target=self._writer_worker)
        self.writer_thread.start()
        
        # Start the audio stream
        try:
            self.stream = sd.InputStream(
                device=self.device_id,
                channels=self.config.channels,
                samplerate=self.config.sample_rate,
                dtype=self.config.dtype,
                blocksize=1024,
                callback=self._audio_callback
            )
            self.stream.start()
            print("✓ Audio capture started")
        except Exception as e:
            self.is_recording = False
            raise RuntimeError(f"Failed to start audio stream: {e}")
    
    def stop(self) -> Path:
        """Stop audio capture and return the output directory."""
        if not self.is_recording:
            print("Not recording!")
            return self.output_dir
        
        print("\nStopping audio capture...")
        self.is_recording = False
        
        # Stop the audio stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # Wait for writer thread to finish
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
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(list_file),
                    "-acodec", "pcm_s16le",
                    str(output_path)
                ],
                check=True,
                capture_output=True,
                cwd=self.output_dir
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
    
    parser = argparse.ArgumentParser(description="Test audio capture")
    parser.add_argument("--duration", type=int, default=10, help="Recording duration in seconds")
    parser.add_argument("--output", type=str, default="/tmp/meetscribe_test", help="Output directory")
    parser.add_argument("--concatenate", action="store_true", help="Concatenate chunks after recording")
    args = parser.parse_args()
    
    def print_levels(system, mic):
        """Print audio levels."""
        sys_bar = "█" * int(system * 50)
        mic_bar = "█" * int(mic * 50)
        print(f"\rSystem: [{sys_bar:<50}] Mic: [{mic_bar:<50}]", end="", flush=True)
    
    meeting_id = str(uuid.uuid4())
    capture = AudioCapture(
        meeting_id=meeting_id,
        output_dir=args.output,
        level_callback=print_levels
    )
    
    def signal_handler(sig, frame):
        print("\n\nInterrupted!")
        capture.stop()
        if args.concatenate:
            capture.concatenate_chunks()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"Recording for {args.duration} seconds (Ctrl+C to stop early)...")
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
