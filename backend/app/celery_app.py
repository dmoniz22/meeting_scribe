#!/usr/bin/env python3
"""
Celery application for MeetScribe background tasks.

Tasks:
- transcribe_meeting: Transcribe audio with WhisperX
- generate_embeddings: Create vector embeddings for segments and notes
- summarize_meeting: Generate summary with Ollama
"""

import os
from celery import Celery
from kombu import Queue

# Celery configuration
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery("meetscribe")

# Configure broker and backend
app.conf.update(
    broker_url=redis_url,
    result_backend=redis_url,
    
    # Task queues with priorities
    task_queues=(
        Queue("high", routing_key="high"),
        Queue("default", routing_key="default"),
        Queue("low", routing_key="low"),
    ),
    task_default_queue="default",
    task_default_routing_key="default",
    
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Result settings
    result_expires=3600 * 24,  # 24 hours
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Import tasks to register them
from app.tasks import transcription, embeddings, summarization

# Auto-discover tasks
app.autodiscover_tasks()
