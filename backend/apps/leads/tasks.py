from celery import shared_task

from . import services


@shared_task(bind=True, max_retries=5)
def notify_advertiser_of_lead(self, lead_id: int) -> str:
    """Tell the broker about a new lead on WhatsApp. Idempotent: a sent lead is never resent."""
    try:
        return services.notify_advertiser(lead_id)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            services.mark_notify_failed(lead_id)
            return "failed"
        # Wait 1, 2, 4, 8, then 16 minutes between tries.
        raise self.retry(exc=exc, countdown=60 * 2**self.request.retries) from exc
