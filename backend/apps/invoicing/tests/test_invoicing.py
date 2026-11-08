from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.brokers.tests.factories import BrokerProfileFactory
from apps.invoicing import services
from apps.invoicing.models import Invoice
from apps.invoicing.tasks import issue_invoice as issue_invoice_task
from apps.payments import services as payment_services
from apps.payments.models import Payment, TopUpPackage
from integrations.payments import GatewayStatus
from integrations.payments.mock import MockPaymentsClient
from integrations.zatca import parse_qr_tlv
from integrations.zatca.mock import MockZatcaClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def broker(db):
    return BrokerProfileFactory(name_en="Sara Broker")


@pytest.fixture
def make_paid(broker, monkeypatch):
    monkeypatch.setattr("apps.invoicing.tasks.issue_invoice.delay", lambda *a: None)
    package = TopUpPackage.objects.create(
        name_ar="باقة", name_en="Pack", credits=100, price_halalas=10000
    )

    def _make(user=None):
        payment, _ = payment_services.start_top_up(user or broker.user, package.pk)
        MockPaymentsClient.set_status(payment.gateway_ref, GatewayStatus.PAID)
        return payment_services.confirm_payment(payment)

    return _make


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.parametrize(
    "total, rate, expected",
    [
        (10000, 1500, (8696, 1304)),  # SAR 100.00
        (27000, 1500, (23478, 3522)),  # SAR 270.00
        (80000, 1500, (69565, 10435)),
        (115, 1500, (100, 15)),
        (100, 0, (100, 0)),
    ],
)
def test_split_vat(total, rate, expected):
    assert services.split_vat(total, rate) == expected


def test_issue_invoice(make_paid, settings):
    settings.SELLER_NAME_AR = "منصة تجريبية"
    settings.SELLER_VAT_NUMBER = "310000000000003"
    payment = make_paid()
    invoice = services.issue_invoice(payment)
    year = invoice.issued_at.year
    assert invoice.number == f"INV-{year}-000001"
    assert invoice.buyer_name == "Sara Broker"
    assert (invoice.subtotal_halalas, invoice.vat_halalas, invoice.total_halalas) == (
        8696,
        1304,
        10000,
    )
    assert invoice.zatca_status == Invoice.ZatcaStatus.REPORTED
    qr = parse_qr_tlv(invoice.qr_base64)
    assert qr[1] == "منصة تجريبية"
    assert qr[2] == "310000000000003"
    assert qr[4] == "100.00"
    assert qr[5] == "13.04"


def test_issue_is_idempotent_and_numbers_are_sequential(make_paid):
    first = make_paid()
    second = make_paid()
    a = services.issue_invoice(first)
    assert services.issue_invoice(Payment.objects.get(pk=first.pk)).pk == a.pk
    b = services.issue_invoice(second)
    assert Invoice.objects.count() == 2
    assert int(b.number[-6:]) == int(a.number[-6:]) + 1


def test_unpaid_payment_gets_no_invoice(broker, make_paid):
    paid = make_paid()
    Payment.objects.filter(pk=paid.pk).update(status=Payment.Status.FAILED)
    with pytest.raises(services.InvoiceError):
        services.issue_invoice(Payment.objects.get(pk=paid.pk))


def test_zatca_failure_keeps_invoice_and_retries_later(make_paid):
    payment = make_paid()
    with patch.object(MockZatcaClient, "report_simplified", side_effect=OSError("down")):
        with pytest.raises(OSError):
            services.issue_invoice(payment)
    invoice = Invoice.objects.get()
    assert invoice.zatca_status == Invoice.ZatcaStatus.PENDING
    assert services.issue_invoice(payment).zatca_status == Invoice.ZatcaStatus.REPORTED
    assert Invoice.objects.get().number == invoice.number


def test_task_issues_invoice(make_paid):
    payment = make_paid()
    number = issue_invoice_task.apply(args=[payment.pk]).get()
    assert Invoice.objects.get().number == number


def test_pdf_renders(make_paid):
    invoice = services.issue_invoice(make_paid())
    pdf = services.render_pdf(invoice)
    assert pdf.startswith(b"%PDF")


# --- API ----------------------------------------------------------------------------


def test_invoice_list_and_pdf_are_mine_only(broker, make_paid):
    invoice = services.issue_invoice(make_paid())
    body = api(broker.user).get(reverse("invoices")).json()
    assert [i["number"] for i in body["results"]] == [invoice.number]
    assert body["results"][0]["total_halalas"] == 10000

    response = api(broker.user).get(reverse("invoice-pdf", args=[invoice.pk]))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

    other = BrokerProfileFactory().user
    assert api(other).get(reverse("invoices")).json()["results"] == []
    assert api(other).get(reverse("invoice-pdf", args=[invoice.pk])).status_code == 404


def test_payment_shows_invoice_once_reported(broker, make_paid):
    payment = make_paid()
    url = reverse("topup-detail", args=[payment.pk])
    assert api(broker.user).get(url).json()["invoice_id"] is None
    invoice = services.issue_invoice(payment)
    assert api(broker.user).get(url).json()["invoice_id"] == invoice.pk


def test_admin_pdf(client, make_paid):
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    client.force_login(UserFactory(role=User.Role.STAFF, is_staff=True, is_superuser=True))
    invoice = services.issue_invoice(make_paid())
    admin_client = client
    assert admin_client.get(reverse("admin:invoicing_invoice_changelist")).status_code == 200
    response = admin_client.get(reverse("admin:invoicing_invoice_pdf", args=[invoice.pk]))
    assert response.content.startswith(b"%PDF")
