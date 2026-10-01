from celery import shared_task


@shared_task(time_limit=1800, soft_time_limit=1740)
def process_production(run_id):
    from .services import run_production
    run_production(run_id)
