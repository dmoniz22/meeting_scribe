#!/usr/bin/env python3
"""
capture.py - Dual-stream audio capture for MeetScribe
Uses separate thread-safe ring buffers per stream, decoupled from the writer.
"""

import wave
import time
import subprocess
import struct
import threading
import queue as stdlib_queue
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass
class AudioConfig:
    target_sample_rate: int = 48000
    dtype: str = "float32"
    chunk_duration: int = 30
    system_gain: float = 0.5
    mic_gain: float = 10.0


def rms_of(arr):
    if len(arr) == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr.astype(float) ** 2)))


class RingBuffer:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer = np.zeros(capacity, dtype=np.float32)
        self.write_pos = 0
        self.read_pos = 0
        self.available = 0
        self._lock = threading.Lock()

    def write(self, data: np.ndarray) -> int:
        with self._lock:
            n = len(data)
            if n > self.capacity:
                data = data[-self.capacity :]
                n = len(data)
            end = self.write_pos + n
            if end <= self.capacity:
                self.buffer[self.write_pos : end] = data
            else:
                first = self.capacity - self.write_pos
                self.buffer[self.write_pos :] = data[:first]
                self.buffer[: n - first] = data[first:]
            self.write_pos = end % self.capacity
            self.available = min(self.available + n, self.capacity)
            return n

    def read(self, n: int) -> np.ndarray:
        with self._lock:
            avail = min(n, self.available)
            if avail == 0:
                return np.zeros(n, dtype=np.float32)
            start = self.read_pos
            end = start + avail
            if end <= self.capacity:
                data = self.buffer[start:end].copy()
            else:
                data = np.concatenate(
                    [
                        self.buffer[start:],
                        self.buffer[: avail - (self.capacity - start)],
                    ]
                )
            self.read_pos = end % self.capacity
            self.available -= avail
            if avail < n:
                zeros = np.zeros(n - avail, dtype=np.float32)
                return np.concatenate([data, zeros]) if avail > 0 else zeros
            return data

    def qsize(self) -> int:
        with self._lock:
            return self.available


class AudioCapture:
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

        self.is_recording = False
        self.system_stream: Optional[sd.InputStream] = None
        self.mic_stream: Optional[sd.InputStream] = None
        self.writer_thread: Optional[threading.Thread] = None

        self.current_chunk: int = 0
        self.current_file: Optional[wave.Wave_write] = None
        self.chunk_start_time: Optional[datetime] = None
        self.frames_written: int = 0

        self.current_levels = {"system": 0.0, "mic": 0.0}
        self._level_lock = threading.Lock()

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.system_device_id = self._find_system_device()
        self.mic_device_id = self._find_mic_device()

        print(
            f"  System device: {sd.query_devices(self.system_device_id)['name']} (id: {self.system_device_id})"
        )
        print(
            f"  Mic device: {sd.query_devices(self.mic_device_id)['name']} (id: {self.mic_device_id})"
        )

        sr = self.config.target_sample_rate
        self.system_buffer = RingBuffer(capacity=sr * 60)
        self.mic_buffer = RingBuffer(capacity=sr * 60)
        self.bytes_written = 0

    def _find_system_device(self) -> int:
        names = [
            "Logi USB Headset Analog Stereo",
            "Headset Analog Stereo",
            "Logi USB Headset",
        ]
        devs = sd.query_devices()
        for name in names:
            for i, d in enumerate(devs):
                if (
                    name.lower() in d.get("name", "").lower()
                    and d.get("max_input_channels", 0) >= 2
                ):
                    return i
        for idx in [22, 23, 21]:
            try:
                d = sd.query_devices(idx)
                if d and d.get("max_input_channels", 0) >= 2:
                    return idx
            except Exception:
                pass
        for i, d in enumerate(devs):
            if d.get("max_input_channels", 0) >= 2:
                return i
        return sd.default.device[0]

    def _find_mic_device(self) -> int:
        names = ["Logi USB Headset Mono", "Headset Mono", "USB Headset Mono"]
        devs = sd.query_devices()
        for name in names:
            for i, d in enumerate(devs):
                if (
                    name.lower() in d.get("name", "").lower()
                    and d.get("max_input_channels", 0) >= 1
                ):
                    return i
        for idx in [16, 17, 15]:
            try:
                d = sd.query_devices(idx)
                if d and d.get("max_input_channels", 0) >= 1:
                    return idx
            except Exception:
                pass
        for i, d in enumerate(devs):
            if (
                d.get("max_input_channels", 0) >= 1
                and d.get("max_output_channels", 0) == 0
            ):
                return i
        return sd.default.device[0]

    def _system_callback(self, indata, frames, time_info, status):
        if status:
            return
        if not self.is_recording:
            return

        system = indata[:, 0] * self.config.system_gain
        self.system_buffer.write(system)

        with self._level_lock:
            self.current_levels["system"] = float(rms_of(system))

    def _mic_callback(self, indata, frames, time_info, status):
        if status:
            return
        if not self.is_recording:
            return

        mic = indata[:, 0] if indata.ndim > 1 else indata.flatten()
        mic = mic * self.config.mic_gain
        self.mic_buffer.write(mic)

        with self._level_lock:
            self.current_levels["mic"] = float(rms_of(mic))

        levels = self.current_levels.copy()
        if self.level_callback:
            self.level_callback(levels["system"], levels["mic"])

    def _writer_worker(self):
        print("[WRITER] Starting", flush=True)
        bytes_total = 0
        blocks_total = 0

        while (
            self.is_recording
            or self.system_buffer.qsize() > 0
            or self.mic_buffer.qsize() > 0
        ):
            if self.current_file is None or self._should_rotate_chunk():
                if self.current_file:
                    self.current_file.close()
                    print(f"  Closed chunk {self.current_chunk - 1:03d}", flush=True)
                self._start_new_chunk()

            sys_avail = self.system_buffer.qsize()
            mic_avail = self.mic_buffer.qsize()

            if sys_avail == 0 or mic_avail == 0:
                time.sleep(0.001)
                continue

            n = min(sys_avail, mic_avail, 1024)

            system = self.system_buffer.read(n)
            mic = self.mic_buffer.read(n)

            mono = np.clip((system + mic) * 0.5, -1.0, 1.0)
            audio_int16 = (mono * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            self.current_file.writeframes(audio_bytes)
            self.bytes_written += len(audio_bytes)
            bytes_total += len(audio_bytes)
            blocks_total += 1

        if self.current_file:
            self.current_file.close()
            self.current_file = None
            print(f"  Closed chunk {self.current_chunk - 1:03d}", flush=True)
        print(
            f"[WRITER] Done. bytes={bytes_total}, blocks={blocks_total}, frames={bytes_total // 2}",
            flush=True,
        )

    def _should_rotate_chunk(self) -> bool:
        if not self.chunk_start_time:
            return True
        elapsed = (datetime.now() - self.chunk_start_time).total_seconds()
        return elapsed >= self.config.chunk_duration

    def _start_new_chunk(self):
        chunk_filename = self.output_dir / f"chunk_{self.current_chunk:03d}.wav"
        self.current_file = wave.open(str(chunk_filename), "wb")
        self.current_file.setnchannels(1)
        self.current_file.setsampwidth(2)
        self.current_file.setframerate(self.config.target_sample_rate)
        self.chunk_start_time = datetime.now()
        self.frames_written = 0
        self.current_chunk += 1
        print(f"  Started chunk: {chunk_filename}", flush=True)

    def start(self):
        if self.is_recording:
            return

        print(f"\nStarting capture for {self.meeting_id}", flush=True)
        self.is_recording = True
        self.current_chunk = 0
        self.frames_written = 0
        self.bytes_written = 0
        self.system_buffer = RingBuffer(capacity=self.config.target_sample_rate * 60)
        self.mic_buffer = RingBuffer(capacity=self.config.target_sample_rate * 60)

        self.writer_thread = threading.Thread(target=self._writer_worker, daemon=True)
        self.writer_thread.start()

        self.system_stream = sd.InputStream(
            device=self.system_device_id,
            channels=2,
            samplerate=self.config.target_sample_rate,
            dtype=self.config.dtype,
            blocksize=1024,
            callback=self._system_callback,
        )
        self.mic_stream = sd.InputStream(
            device=self.mic_device_id,
            channels=1,
            samplerate=self.config.target_sample_rate,
            dtype=self.config.dtype,
            blocksize=1024,
            callback=self._mic_callback,
        )
        self.system_stream.start()
        self.mic_stream.start()
        print("Streams started", flush=True)

    def stop(self) -> Path:
        if not self.is_recording:
            return self.output_dir

        print("\nStopping capture...", flush=True)
        self.is_recording = False

        if self.system_stream:
            self.system_stream.stop()
            self.system_stream.close()
            self.system_stream = None
        if self.mic_stream:
            self.mic_stream.stop()
            self.mic_stream.close()
            self.mic_stream = None
        if self.writer_thread:
            self.writer_thread.join(timeout=10.0)

        print(
            f"Captured {self.current_chunk} chunk(s), {self.bytes_written} bytes",
            flush=True,
        )
        return self.output_dir

    def get_current_levels(self) -> dict:
        with self._level_lock:
            return self.current_levels.copy()

    def concatenate_chunks(self, output_filename: str = "full_recording.wav") -> Path:
        output_path = self.output_dir / output_filename
        chunk_list = sorted(self.output_dir.glob("chunk_*.wav"))
        if not chunk_list:
            return output_path

        print(f"Concatenating {len(chunk_list)} chunks...")
        list_file = self.output_dir / "chunks.txt"
        with open(list_file, "w") as f:
            for chunk in chunk_list:
                f.write(f"file '{chunk.name}'\n")

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
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                cwd=self.output_dir,
            )
            print(f"Created {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error: {e.stderr.decode() if e.stderr else e}")
        finally:
            list_file.unlink(missing_ok=True)

        return output_path
