from celery import shared_task

from tts.providers.base import ProviderTemporaryError

from .services import run_generation_job


@shared_task(
    bind=True,
    autoretry_for=(ProviderTemporaryError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def generate_audio(self, job_id):
    run_generation_job(job_id)

