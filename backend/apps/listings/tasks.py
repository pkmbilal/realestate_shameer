from celery import shared_task

from apps.core.models import IntegrationError
from apps.core.services import record_integration_error

from . import services
from .models import Listing


@shared_task
def expire_listings() -> int:
    """Nightly (see CELERY_BEAT_SCHEDULE): hide listings whose licence or post period ended."""
    return services.expire_due_listings()


@shared_task
def resync_active_licences() -> dict:
    """Nightly, before expire_listings: re-check every live licence with REGA."""
    return services.resync_active_licences()


@shared_task
def warn_expiring_listings() -> int:
    """Daily: queue a WhatsApp warning for each listing that comes down within 3 days."""
    due = services.listings_to_warn()
    for listing in due:
        send_listing_expiry_warning.delay(listing.pk)
    return len(due)


@shared_task(bind=True, max_retries=5)
def send_listing_expiry_warning(self, listing_id: int) -> str:
    """Send one expiry warning. Idempotent: each expiry date is warned about only once."""
    try:
        return services.send_expiry_warning(listing_id)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            reference = (
                Listing.objects.filter(pk=listing_id).values_list("reference", flat=True).first()
            )
            record_integration_error(
                IntegrationError.Integration.WHATSAPP,
                "send_expiry_warning",
                exc,
                reference=f"listing:{reference or listing_id}",
            )
            return "failed"
        # Wait 1, 2, 4, 8, then 16 minutes between tries.
        raise self.retry(exc=exc, countdown=60 * 2**self.request.retries) from exc
