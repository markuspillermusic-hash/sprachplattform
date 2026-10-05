from celery import shared_task


@shared_task(time_limit=180, soft_time_limit=150)
def process_worksheet(worksheet_id):
    from .services import generate_worksheet
    generate_worksheet(worksheet_id)
