from unittest.mock import MagicMock

import pytest

from apps.brokers.tests.factories import BrokerProfileFactory
from apps.payments.models import TopUpPackage
from integrations.payments import GatewayStatus
from integrations.payments.mock import MockPaymentsClient


@pytest.fixture
def broker(db):
    return BrokerProfileFactory()


@pytest.fixture
def package(db):
    return TopUpPackage.objects.create(
        name_ar="باقة", name_en="Test pack", credits=100, price_halalas=10000
    )


@pytest.fixture
def invoice_queued(monkeypatch):
    """Stand-in for the invoice task, so payment tests don't render PDFs."""
    delay = MagicMock()
    monkeypatch.setattr("apps.invoicing.tasks.issue_invoice.delay", delay)
    return delay


@pytest.fixture
def gateway():
    """Drive the mock gateway: gateway.pay(payment) / gateway.fail(payment)."""

    class Gateway:
        @staticmethod
        def pay(payment):
            MockPaymentsClient.set_status(payment.gateway_ref, GatewayStatus.PAID)

        @staticmethod
        def fail(payment):
            MockPaymentsClient.set_status(payment.gateway_ref, GatewayStatus.FAILED)

    return Gateway()
