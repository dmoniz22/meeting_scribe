#!/usr/bin/env python3
"""
audio_router.py - Minimal audio routing for MeetScribe recording using PipeWire

Note: Dual-stream capture now captures directly from:
  - System audio: "Logi USB Headset Analog Stereo" (device 22) - headset monitor
  - Mic: "Logi USB Headset Mono" (device 16)
No virtual sink is needed.
"""

import subprocess
import logging
import json
import re
from typing import Optional

logger = logging.getLogger(__name__)

HEADSET_SINK = "alsa_output.usb-Logitech_Logi_USB_Headset_000000000000-00.analog-stereo"
MIC_SOURCE = "alsa_input.usb-Logitech_Logi_USB_Headset_000000000000-00.mono-fallback"
CAPTURE_SINK_NAME = "meetscribe_capture"


def run_cmd(cmd, capture=True):
    """Run a shell command and return output."""
    if isinstance(cmd, str):
        cmd = cmd.split()
    result = subprocess.run(cmd, capture_output=capture, text=True)
    return result


def find_node_id_by_nick(nick: str) -> Optional[str]:
    """Find PipeWire node ID by nickname, name, or description."""
    result = run_cmd(["pw-cli", "ls", "Node"])
    if result.returncode != 0:
        return None

    lines = result.stdout.split("\n")
    for i, line in enumerate(lines):
        if (
            f'"{nick}"' in line
            or f'node.name = "{nick}"' in line
            or f'node.description = "{nick}"' in line
        ):
            # ID line is right after the node block starts (2-6 lines before description)
            for j in range(max(0, i - 8), i):
                if re.search(r"id\s+\d+", lines[j]):
                    return re.search(r"id\s+(\d+)", lines[j]).group(1)
    return None


def get_default_sink_id() -> Optional[str]:
    """Get the current default sink ID."""
    result = run_cmd(["wpctl", "status"])
    if result.returncode != 0:
        return None

    for line in result.stdout.split("\n"):
        if (
            "*" in line
            and "Audio/Sink"
            in result.stdout[result.stdout.find(line) : result.stdout.find(line) + 200]
        ):
            match = re.match(r"\s*(\d+)\.", line.strip())
            if match:
                return match.group(1)
    return None


def get_default_source_id() -> Optional[str]:
    """Get the current default source ID."""
    result = run_cmd(["wpctl", "status"])
    if result.returncode != 0:
        return None

    lines = result.stdout.split("\n")
    in_sources = False
    for line in lines:
        if "Sources:" in line:
            in_sources = True
            continue
        if in_sources and line.strip().startswith("Sinks:"):
            break
        if in_sources and "*" in line:
            match = re.match(r"\s*(\d+)\.", line.strip())
            if match:
                return match.group(1)
    return None


def set_default_sink(sink_id: str) -> bool:
    """Set the default sink by ID."""
    result = run_cmd(["wpctl", "set-default", sink_id])
    return result.returncode == 0


def set_default_source(source_id: str) -> bool:
    """Set the default source by ID."""
    result = run_cmd(["wpctl", "set-default", source_id])
    return result.returncode == 0


def find_headset_sink_id() -> Optional[str]:
    """Find the Logitech headset sink ID."""
    node_id = find_node_id_by_nick("Logi USB Headset Analog Stereo")
    if not node_id:
        node_id = find_node_id_by_nick("Logi USB Headset")
    if not node_id:
        node_id = find_node_id_by_nick(HEADSET_SINK)
    return node_id


def find_headset_mic_id() -> Optional[str]:
    """Find the Logitech headset mic source ID."""
    node_id = find_node_id_by_nick("Logi USB Headset Mono")
    if not node_id:
        node_id = find_node_id_by_nick("Headset Mono")
    if not node_id:
        node_id = find_node_id_by_nick(MIC_SOURCE)
    return node_id


def setup_recording_routing():
    """
    Set up audio routing for recording.

    With dual-stream capture, no virtual sink is needed.
    This function ensures:
    1. Headset is set as the default sink (so all apps output to it)
    2. Headset mic is set as the default source
    """
    print("Setting up PipeWire audio routing for recording...")

    headset_sink_id = find_headset_sink_id()
    if headset_sink_id:
        result = run_cmd(["wpctl", "set-default", headset_sink_id])
        if result.returncode == 0:
            print(f"  Set headset as default sink (ID: {headset_sink_id})")
        else:
            print(f"  Warning: Could not set default sink: {result.stderr}")
    else:
        print("  Warning: Could not find headset sink")

    headset_mic_id = find_headset_mic_id()
    if headset_mic_id:
        result = run_cmd(["wpctl", "set-default", headset_mic_id])
        if result.returncode == 0:
            print(f"  Set headset mic as default source (ID: {headset_mic_id})")
        else:
            print(f"  Warning: Could not set default source: {result.stderr}")
    else:
        print("  Warning: Could not find headset mic")

    print("  Note: Dual-stream capture uses devices:")
    print(f"    System audio: Logi USB Headset Analog Stereo (device 22)")
    print(f"    Mic: Logi USB Headset Mono (device 16)")
    print("✓ Routing configured")
    return True


def cleanup_routing():
    """Clean up audio routing after recording stops."""
    print("Cleaning up PipeWire audio routing...")
    print("✓ No virtual sink to remove (using direct device capture)")
    return True


def get_routing_status():
    """Get current routing status."""
    status = {
        "pipewire_active": False,
        "headset_sink_id": None,
        "headset_mic_id": None,
        "default_sink_id": None,
        "default_source_id": None,
    }

    result = run_cmd(["pw-cli", "info", "0"])
    status["pipewire_active"] = result.returncode == 0

    status["headset_sink_id"] = find_headset_sink_id()
    status["headset_mic_id"] = find_headset_mic_id()
    status["default_sink_id"] = get_default_sink_id()
    status["default_source_id"] = get_default_source_id()

    return status


def diagnose():
    """Diagnose current PipeWire audio state."""
    print("=== PipeWire Audio Diagnosis ===\n")

    print("--- Default Devices ---")
    sink = get_default_sink_id()
    source = get_default_source_id()
    print(f"  Default Sink: {sink}")
    print(f"  Default Source: {source}")

    print("\n--- Headset Devices ---")
    hs_sink = find_headset_sink_id()
    hs_mic = find_headset_mic_id()
    print(f"  Headset Sink ID: {hs_sink}")
    print(f"  Headset Mic ID: {hs_mic}")

    print("\n--- All Sinks ---")
    result = run_cmd(["wpctl", "status"])
    in_sinks = False
    for line in result.stdout.split("\n"):
        if "Sinks:" in line:
            in_sinks = True
            continue
        if in_sinks and ("Sources:" in line or "Filters:" in line):
            break
        if in_sinks and line.strip() and not line.startswith(" "):
            break
        if in_sinks and line.strip():
            print(f"  {line.strip()}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            setup_recording_routing()
        elif sys.argv[1] == "cleanup":
            cleanup_routing()
        elif sys.argv[1] == "status":
            print(json.dumps(get_routing_status(), indent=2))
        elif sys.argv[1] == "diagnose":
            diagnose()
    else:
        print("Usage: audio_router.py {setup|cleanup|status|diagnose}")
