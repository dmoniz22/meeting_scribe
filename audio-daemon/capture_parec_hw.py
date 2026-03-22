#!/usr/bin/env python3
"""
capture_parec_hw.py - Audio capture module for MeetScribe using hardware devices
Captures audio directly from:
1. System output monitor (desktop audio)
2. Microphone input

Mixed and written to WAV files.
"""
import wave
import time
import os
import subprocess
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass
import threading
import queue
import numpy as np

@dataclass
class AudioConfig:
    """Configuration for audio capture."""
    target_sample_rate: int = 16000  # Output rate for Whisper
    capture_sample_rate: int = 48000  # Standard system rate
    channels: int = 2
    chunk_duration: int = 30  # seconds per WAV file
    # Devices (auto-detected if not set)
    system_audio_source: Optional[str] = None  # e.g., "alsa_output.***.monitor"
    microphone_source: Optional[str] = None    # e.g., "alsa_input.***"


class AudioCaptureHW:
    """
    Captures audio from hardware sources using parec and writes to WAV files.
    Captures both system audio and microphone simultaneously.
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
        self.system_process: Optional[subprocess.Popen] = None
        self.mic_process: Optional[subprocess.Popen] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.audio_queue: queue.Queue = queue.Queue(maxsize=100)
        
        # Auto-detect sources if not set
        if not self.config.system_audio_source or not self.config.microphone_source:
            self._detect_sources()
        
        # File management
        self.current_chunk: int = 0
        self.current_file: Optional[wave.Wave_write] = None
        self.frames_written: int = 0
        self.chunk_start_time: Optional[datetime] = None
        
        # Level monitoring
        self.current_levels = {"system": 0.0, "mic": 0.0}
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Audio format
        self.sample_width = 2  # 16-bit
        
    def _detect_sources(self):
        """Auto-detect system audio and microphone sources."""
        try:
            # Get default sink monitor (system audio)
            result = subprocess.run(
                ["pactl", "info"], capture_output=True, text=True
            )
            for line in result.stdout.split('\n'):
                if "Default Sink:" in line:
                    sink = line.split(":")[1].strip()
                    self.config.system_audio_source = f"{sink}.monitor"
                    print(f"[Audio] System audio: {self.config.system_audio_source}")
                if "Default Source:" in line:
                    self.config.microphone_source = line.split(":")[1].strip()
                    print(f"[Audio] Microphone: {self.config.microphone_source}")
        except Exception as e:
            print(f"[Audio] Error detecting sources: {e}")
    
    def _build_parec_cmd(self, device: str) -> List[str]:
        """Build parec command for a device."""
        return [
            "parec",
            "--device", device,
            "--rate", str(self.config.capture_sample_rate),
            "--channels", str(self.config.channels),
            "--format", "s16ne",  # signed 16-bit native endian
            "--latency", "4096"
        ]
    
    def _calculate_rms(self, audio_data: np.ndarray) -> tuple[float, float]:
        """Calculate RMS levels for left and right channels."""
        if audio_data.size == 0:
            return 0.0, 0.0
        
        # Split channels
        if audio_data.ndim > 1 and audio_data.shape[1] >= 2:
            left_channel = audio_data[:, 0]
            right_channel = audio_data[:, 1]
        else:
            left_channel = right_channel = audio_data.flatten()
        
        # Calculate RMS
        rms_left = np.sqrt(np.mean(left_channel ** 2))
        rms_right = np.sqrt(np.mean(right_channel ** 2))
        
        return float(rms_left), float(rms_right)
    
    def _capture_worker(self, device: str, source_name: str):
        """Background thread that reads from parec and puts data in queue."""
        cmd = self._build_parec_cmd(device)
        print(f"[{source_name}] Starting: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            if source_name == "system":
                self.system_process = process
            else:
                self.mic_process = process
            
            frame_size = self.config.channels * self.sample_width
            chunk_bytes = 1024 * frame_size  # ~43ms at 48kHz stereo
            
            while self.is_recording and process.poll() is None:
                try:
                    raw_data = process.stdout.read(chunk_bytes)
                    if not raw_data:
                        time.sleep(0.001)
                        continue
                    
                    # Convert to float32
                    num_samples = len(raw_data) // self.sample_width
                    fmt = f"{num_samples}h"
                    samples = struct.unpack(fmt, raw_data[:num_samples * self.sample_width])
                    audio_int16 = np.array(samples, dtype=np.int16)
                    
                    if self.config.channels > 1:
                        audio_int16 = audio_int16.reshape(-1, self.config.channels)
                    
                    audio_float32 = audio_int16.astype(np.float32) / 32768.0
                    
                    # Calculate levels
                    if source_name == "system":
                        system_level, _ = self._calculate_rms(audio_float32)
                        self.current_levels["system"] = system_level
                    else:
                        mic_level, _ = self._calculate_rms(audio_float32)
                        self.current_levels["mic"] = mic_level
                    
                    if self.level_callback:
                        self.level_callback(
                            self.current_levels["system"],
                            self.current_levels["mic"]
                        )
                    
                    # Queue with source tag
                    try:
                        self.audio_queue.put({
                            "source": source_name,
                            "data": audio_float32
                        }, timeout=1.0)
                    except queue.Full:
                        print(f"[{source_name}] Queue full")
                        
                except Exception as e:
                    if self.is_recording:
                        print(f"[{source_name}] Error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{source_name}] Failed to start: {e}")
        finally:
            if process:
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()