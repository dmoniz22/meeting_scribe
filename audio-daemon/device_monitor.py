#!/usr/bin/env python3
"""
device_monitor.py - Monitor PipeWire audio device changes

This module monitors PipeWire for audio device changes (headphones plugged/unplugged)
and automatically reconfigures the MeetScribe virtual sink routing.

Usage:
    from device_monitor import DeviceMonitor
    monitor = DeviceMonitor()
    monitor.start()
    # ... monitoring ...
    monitor.stop()
"""

import subprocess
import json
import time
import threading
from typing import Optional, Callable, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AudioDevice:
    """Represents an audio device."""
    id: int
    name: str
    description: str
    device_type: str  # 'sink' or 'source'
    is_default: bool = False


class DeviceMonitor:
    """
    Monitors PipeWire audio device changes.
    
    Features:
    - Detects when default audio devices change
    - Automatically restarts MeetScribe loopback modules
    - Provides callbacks for device change events
    """
    
    def __init__(
        self,
        on_device_change: Optional[Callable[[str, AudioDevice], None]] = None,
        check_interval: float = 2.0
    ):
        self.on_device_change = on_device_change
        self.check_interval = check_interval
        
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Track current default devices
        self.current_sink: Optional[str] = None
        self.current_source: Optional[str] = None
        
        # Setup script path
        self.setup_script = Path(__file__).parent / "setup_pipewire.sh"
    
    def _get_default_sink(self) -> Optional[str]:
        """Get the current default output device (sink)."""
        try:
            result = subprocess.run(
                ["pactl", "info"],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.split("\n"):
                if "Default Sink:" in line:
                    return line.split(":", 1)[1].strip()
        except Exception as e:
            print(f"Error getting default sink: {e}")
        return None
    
    def _get_default_source(self) -> Optional[str]:
        """Get the current default input device (source)."""
        try:
            result = subprocess.run(
                ["pactl", "info"],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.split("\n"):
                if "Default Source:" in line:
                    return line.split(":", 1)[1].strip()
        except Exception as e:
            print(f"Error getting default source: {e}")
        return None
    
    def _restart_loopbacks(self):
        """Restart the MeetScribe PipeWire setup."""
        print("Device change detected - restarting MeetScribe audio routing...")
        
        try:
            if self.setup_script.exists():
                result = subprocess.run(
                    ["bash", str(self.setup_script)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(result.stdout)
                if result.stderr:
                    print(f"Warnings: {result.stderr}")
            else:
                print(f"Setup script not found: {self.setup_script}")
        except subprocess.CalledProcessError as e:
            print(f"Error restarting loopbacks: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        print("Device monitor started")
        
        # Get initial device states
        self.current_sink = self._get_default_sink()
        self.current_source = self._get_default_source()
        
        print(f"Initial sink: {self.current_sink}")
        print(f"Initial source: {self.current_source}")
        
        while self.is_monitoring:
            try:
                # Check for sink changes
                new_sink = self._get_default_sink()
                if new_sink and new_sink != self.current_sink:
                    print(f"Default sink changed: {self.current_sink} -> {new_sink}")
                    self.current_sink = new_sink
                    self._restart_loopbacks()
                    if self.on_device_change:
                        self.on_device_change("sink", AudioDevice(
                            id=0, name=new_sink, description=new_sink,
                            device_type="sink", is_default=True
                        ))
                
                # Check for source changes
                new_source = self._get_default_source()
                if new_source and new_source != self.current_source:
                    print(f"Default source changed: {self.current_source} -> {new_source}")
                    self.current_source = new_source
                    self._restart_loopbacks()
                    if self.on_device_change:
                        self.on_device_change("source", AudioDevice(
                            id=0, name=new_source, description=new_source,
                            device_type="source", is_default=True
                        ))
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(self.check_interval)
        
        print("Device monitor stopped")
    
    def start(self):
        """Start monitoring for device changes."""
        if self.is_monitoring:
            print("Monitor already running")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.start()
        print("✓ Device monitoring started")
    
    def stop(self):
        """Stop monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        print("✓ Device monitoring stopped")
    
    def get_current_devices(self) -> dict:
        """Get current default devices."""
        return {
            "sink": self.current_sink or self._get_default_sink(),
            "source": self.current_source or self._get_default_source()
        }


# CLI for testing
if __name__ == "__main__":
    import signal
    import sys
    
    def on_change(device_type: str, device: AudioDevice):
        print(f"\n[EVENT] {device_type} changed: {device.name}")
    
    monitor = DeviceMonitor(on_device_change=on_change)
    
    def signal_handler(sig, frame):
        print("\n\nStopping monitor...")
        monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Device Monitor Test")
    print("===================")
    print("Monitoring for audio device changes...")
    print("(Plug/unplug headphones to test)")
    print("Press Ctrl+C to exit\n")
    
    monitor.start()
    
    # Keep running
    while True:
        time.sleep(1)
