#!/usr/bin/env python3
"""Patch whisperx for compatibility with faster-whisper 1.1.1+ and broken S3 VAD URL."""

import os
import sys


def patch_vad():
    """Patch whisperx/vad.py to use HuggingFace instead of broken S3 URL."""
    path = "/usr/local/lib/python3.12/dist-packages/whisperx/vad.py"
    if not os.path.exists(path):
        print(f"  {path} not found, skipping")
        return

    with open(path) as f:
        content = f.read()

    if (
        "hf_hub_download" in content
        and "hashlib" not in content.split("hf_hub_download")[1].split("\n\n")[0]
    ):
        print("  vad.py already patched")
        return

    # Replace download + hash check block
    old = """    if not os.path.isfile(model_fp):
        with urllib.request.urlopen(VAD_SEGMENTATION_URL) as source, open(model_fp, "wb") as output:
            with tqdm(
                total=int(source.info().get("Content-Length")),
                ncols=80,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as loop:
                while True:
                    buffer = source.read(8192)
                    if not buffer:
                        break

                    output.write(buffer)
                    loop.update(len(buffer))

    model_bytes = open(model_fp, "rb").read()
    if hashlib.sha256(model_bytes).hexdigest() != VAD_SEGMENTATION_URL.split("/")[-2]:
        raise RuntimeError(
            "Model has been downloaded but the SHA256 checksum does not not match. Please retry loading the model."
        )"""

    new = """    if not os.path.isfile(model_fp):
        try:
            from huggingface_hub import hf_hub_download, login
            token = use_auth_token or os.environ.get('HF_TOKEN')
            if token:
                login(token=token)
            downloaded = hf_hub_download('pyannote/segmentation-3.0', 'pytorch_model.bin', token=token)
            import shutil
            shutil.copy2(downloaded, model_fp)
        except Exception as e:
            raise RuntimeError(
                f'Failed to download VAD model: {e}. '
                'Accept pyannote terms at https://huggingface.co/pyannote/segmentation-3.0'
            )"""

    if old in content:
        content = content.replace(old, new)
        with open(path, "w") as f:
            f.write(content)
        print("  vad.py patched (string replace)")
    else:
        # Fallback: line-by-line patch
        with open(path) as f:
            lines = f.readlines()
        new_lines = []
        skip = False
        for line in lines:
            if "with urllib.request.urlopen(VAD_SEGMENTATION_URL)" in line:
                skip = True
                new_lines.extend(
                    [
                        "    if not os.path.isfile(model_fp):\n",
                        "        try:\n",
                        "            from huggingface_hub import hf_hub_download, login\n",
                        "            token = use_auth_token or os.environ.get('HF_TOKEN')\n",
                        "            if token: login(token=token)\n",
                        "            downloaded = hf_hub_download('pyannote/segmentation-3.0', 'pytorch_model.bin', token=token)\n",
                        "            import shutil; shutil.copy2(downloaded, model_fp)\n",
                        "        except Exception as e:\n",
                        "            raise RuntimeError(f'VAD download failed: {e}')\n",
                    ]
                )
                continue
            if skip:
                if "model_bytes" in line or "hashlib" in line or "checksum" in line:
                    continue
                if line.strip() == "" or line.strip() == ")":
                    skip = False
                    continue
                continue
            new_lines.append(line)
        with open(path, "w") as f:
            f.writelines(new_lines)
        print("  vad.py patched (line-by-line)")


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
    print("Patching whisperx...")
    patch_vad()
    patch_asr()
    print("Done!")
