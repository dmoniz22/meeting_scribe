#!/usr/bin/env python3
"""Patch whisperx for compatibility with faster-whisper 1.1.1+ and broken S3 VAD URL."""

import os
import subprocess


def run(cmd):
    print(f"  Running: {cmd[:80]}...", flush=True)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        print(f"  Warning: {result.stderr.strip()[:200]}")
    return result.returncode == 0


def patch_vad():
    """Patch whisperx/vad.py to use HuggingFace instead of broken S3 URL."""
    path = "/usr/local/lib/python3.12/dist-packages/whisperx/vad.py"
    if not os.path.exists(path):
        print(f"  {path} not found, skipping")
        return

    with open(path) as f:
        content = f.read()

    if "hf_hub_download" in content and "urllib.request.urlopen" not in content:
        print("  vad.py already patched")
        return

    # Use Python to do the replacement reliably
    start_marker = "def load_vad_model(device, vad_onset=0.500, vad_offset=0.363, use_auth_token=None, model_fp=None):"
    end_marker = "class Binarize:"

    if start_marker not in content or end_marker not in content:
        print("  vad.py markers not found, skipping")
        return

    start_idx = content.index(start_marker)
    end_idx = content.index(end_marker)

    new_func = """def load_vad_model(device, vad_onset=0.500, vad_offset=0.363, use_auth_token=None, model_fp=None):
    model_dir = torch.hub._get_torch_home()
    os.makedirs(model_dir, exist_ok = True)
    if model_fp is None:
        model_fp = os.path.join(model_dir, "whisperx-vad-segmentation.bin")
    if os.path.exists(model_fp) and not os.path.isfile(model_fp):
        raise RuntimeError(f"{model_fp} exists and is not a regular file")
    if not os.path.isfile(model_fp):
        try:
            from huggingface_hub import hf_hub_download, login
            token = use_auth_token or os.environ.get("HF_TOKEN")
            if token: login(token=token)
            downloaded = hf_hub_download("pyannote/segmentation-3.0", "pytorch_model.bin", token=token)
            import shutil; shutil.copy2(downloaded, model_fp)
        except Exception as e:
            raise RuntimeError(f"VAD download failed: {e}. Accept pyannote terms at https://huggingface.co/pyannote/segmentation-3.0")
    vad_model = Model.from_pretrained(model_fp, use_auth_token=use_auth_token)
    try:
        hyperparameters = {"onset": vad_onset,
                        "offset": vad_offset,
                        "min_duration_on": 0.1,
                        "min_duration_off": 0.1}
        vad_pipeline = VoiceActivitySegmentation(segmentation=vad_model, device=torch.device(device))
        vad_pipeline.instantiate(hyperparameters)
    except ValueError:
        vad_pipeline = VoiceActivitySegmentation(segmentation=vad_model, device=torch.device(device))
        vad_pipeline.instantiate({})
    return vad_pipeline

"""

    new_content = content[:start_idx] + new_func + content[end_idx:]

    with open(path, "w") as f:
        f.write(new_content)
    print("  vad.py patched")


def patch_asr():
    """Patch whisperx/asr.py to add missing multilingual and hotwords options."""
    path = "/usr/local/lib/python3.12/dist-packages/whisperx/asr.py"
    if not os.path.exists(path):
        print(f"  {path} not found, skipping")
        return

    with open(path) as f:
        content = f.read()

    if '"multilingual"' in content and '"hotwords"' in content:
        print("  asr.py already patched")
        return

    old = "default_asr_options =  {"
    new = 'default_asr_options =  {\n        "multilingual": False,\n        "hotwords": None,'
    content = content.replace(old, new, 1)

    with open(path, "w") as f:
        f.write(content)
    print("  asr.py patched")


if __name__ == "__main__":
    print("Patching whisperx...", flush=True)
    patch_vad()
    patch_asr()
    print("Done!", flush=True)
