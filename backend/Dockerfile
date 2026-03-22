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

EXPOSE 8000

CMD ["sh", "-c", "python3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 & celery -A app.celery_app worker -l info -Q high,default,low --concurrency=2; wait"]
