import logging

from celery import shared_task

from apps.payments.models import Payment

from . import services

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=8)
def issue_invoice(self, payment_id: int) -> str:
    """Issue the e-invoice for a paid top-up. Idempotent: an issued invoice is never duplicated."""
    payment = Payment.objects.select_related("wallet").get(pk=payment_id)
    try:
        return services.issue_invoice(payment).number
    except services.InvoiceError:
        raise
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.error("payment %s: invoice could not be reported to ZATCA", payment_id)
            raise
        # Wait 1, 2, 4 … minutes between tries.
        raise self.retry(exc=exc, countdown=60 * 2**self.request.retries) from exc
