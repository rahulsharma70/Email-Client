"""
Celery Configuration for ANAGHA SOLUTION
Background task processing
"""

from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Redis configuration
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'anagha_solution',
    broker=redis_url,
    backend=redis_url
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

# Task routes
celery_app.conf.task_routes = {
    'core.tasks.send_email_task': {'queue': 'email_sending'},
    'core.tasks.verify_email_task': {'queue': 'email_verification'},
    'core.tasks.scrape_leads_task': {'queue': 'lead_scraping'},
    'core.tasks.warmup_task': {'queue': 'warmup'},
    'core.tasks.monitor_inbox_task': {'queue': 'monitoring'},
}

