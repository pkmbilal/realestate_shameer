from celery import shared_task

from . import services


@shared_task
def expire_listings() -> int:
    """Nightly (see CELERY_BEAT_SCHEDULE): hide listings whose licence or post period ended."""
    return services.expire_due_listings()
