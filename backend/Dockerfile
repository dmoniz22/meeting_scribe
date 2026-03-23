FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    ffmpeg \
    git \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

COPY requirements.txt requirements.worker.txt ./

RUN pip install --no-cache-dir -r requirements.worker.txt

COPY . .

RUN chmod +x /app/start_api.sh

# Pin faster-whisper compatible with whisperx 3.1.6
RUN pip install --no-cache-dir "faster-whisper==1.1.1"

# Patch whisperx for broken S3 VAD URL and faster-whisper compatibility
RUN python3.12 /app/patch_whisperx.py
# Fix pyannote 3.1 VAD parameter incompatibility
RUN python3.12 -c "
path = '/usr/local/lib/python3.12/dist-packages/whisperx/vad.py'
with open(path) as f:
    content = f.read()
# Replace load_vad_model with HuggingFace download and pyannote 3.1 compatible params
start_marker = 'def load_vad_model(device, vad_onset=0.500, vad_offset=0.363, use_auth_token=None, model_fp=None):'
end_marker = 'class Binarize:'
start_idx = content.index(start_marker)
end_idx = content.index(end_marker)
old_func = content[start_idx:end_idx]
new_func = '''def load_vad_model(device, vad_onset=0.500, vad_offset=0.363, use_auth_token=None, model_fp=None):
    model_dir = torch.hub._get_torch_home()
    os.makedirs(model_dir, exist_ok = True)
    if model_fp is None:
        model_fp = os.path.join(model_dir, \"whisperx-vad-segmentation.bin\")
    if os.path.exists(model_fp) and not os.path.isfile(model_fp):
        raise RuntimeError(f\"{model_fp} exists and is not a regular file\")
    if not os.path.isfile(model_fp):
        from huggingface_hub import hf_hub_download, login
        token = use_auth_token or os.environ.get(\"HF_TOKEN\")
        if token: login(token=token)
        downloaded = hf_hub_download(\"pyannote/segmentation-3.0\", \"pytorch_model.bin\", token=token)
        import shutil; shutil.copy2(downloaded, model_fp)
    vad_model = Model.from_pretrained(model_fp, use_auth_token=use_auth_token)
    try:
        hyperparameters = {\"onset\": vad_onset,
                        \"offset\": vad_offset,
                        \"min_duration_on\": 0.1,
                        \"min_duration_off\": 0.1}
        vad_pipeline = VoiceActivitySegmentation(segmentation=vad_model, device=torch.device(device))
        vad_pipeline.instantiate(hyperparameters)
    except ValueError:
        vad_pipeline = VoiceActivitySegmentation(segmentation=vad_model, device=torch.device(device))
        vad_pipeline.instantiate({})
    return vad_pipeline

'''
content = content.replace(old_func, new_func)
with open(path, 'w') as f:
    f.write(content)
print('vad.py patched')
"
# Patch asr.py for faster-whisper compatibility
RUN python3.12 -c "
path = '/usr/local/lib/python3.12/dist-packages/whisperx/asr.py'
with open(path) as f:
    content = f.read()
old = 'default_asr_options =  {'
new = 'default_asr_options =  {\n        \"multilingual\": False,\n        \"hotwords\": None,'
content = content.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(content)
print('asr.py patched')
"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["sh", "-c", "/app/start_api.sh & celery -A app.celery_app worker -l info -Q high,default,low --concurrency=2; wait"]
