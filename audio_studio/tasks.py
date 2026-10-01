from celery import shared_task
from .services import run_job


@shared_task
def process_audio(job_id):
    # Generation has no automatic retry: avoid duplicate provider charges.
    run_job(job_id)
