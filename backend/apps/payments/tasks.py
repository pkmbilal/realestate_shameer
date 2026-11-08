from celery import shared_task

from . import services


@shared_task
def expire_stale_payments() -> int:
    """Every 15 minutes (see CELERY_BEAT_SCHEDULE): settle or expire abandoned checkouts."""
    return services.expire_stale_payments()
