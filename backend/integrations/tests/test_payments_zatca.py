import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from integrations.payments import GatewayStatus, WebhookError, get_payments_client
from integrations.payments.live import LivePaymentsClient
from integrations.payments.mock import MockPaymentsClient
from integrations.zatca import InvoiceData, build_qr_tlv, get_zatca_client, parse_qr_tlv
from integrations.zatca.base import halalas_to_sar
from integrations.zatca.live import LiveZatcaClient
from integrations.zatca.mock import MockZatcaClient


def test_clients_follow_mode(settings):
    assert isinstance(get_payments_client(), MockPaymentsClient)
    assert isinstance(get_zatca_client(), MockZatcaClient)
    settings.INTEGRATIONS_MODE = "live"
    assert isinstance(get_payments_client(), LivePaymentsClient)
    assert isinstance(get_zatca_client(), LiveZatcaClient)


def test_mock_checkout_lifecycle():
    client = MockPaymentsClient()
    checkout = client.create_checkout(
        amount_halalas=500, description="x", return_url="http://site/r?payment=1", metadata={}
    )
    assert client.fetch(checkout.ref).status == GatewayStatus.PENDING
    back = MockPaymentsClient.set_status(checkout.ref, GatewayStatus.PAID)
    assert back == "http://site/r?payment=1&status=paid"
    result = client.fetch(checkout.ref)
    assert (result.status, result.amount_halalas, result.currency) == ("paid", 500, "SAR")
    assert client.fetch("unknown").status == GatewayStatus.FAILED
    assert MockPaymentsClient.set_status("unknown", "paid") is None


def test_parse_webhook(settings):
    settings.MOYASAR_WEBHOOK_SECRET = "abc"
    client = MockPaymentsClient()
    assert client.parse_webhook({"secret_token": "abc", "data": {"invoice_id": "inv_1"}}) == "inv_1"
    for bad in ({"secret_token": "abd", "data": {"invoice_id": "x"}}, {"secret_token": "abc"}):
        with pytest.raises(WebhookError):
            client.parse_webhook(bad)
    settings.MOYASAR_WEBHOOK_SECRET = ""
    with pytest.raises(WebhookError):
        client.parse_webhook({"secret_token": "", "data": {"invoice_id": "x"}})


def _fake_response(data):
    response = MagicMock()
    response.read.return_value = json.dumps(data).encode()
    response.__enter__.return_value = response
    return response


def test_live_client_needs_key(settings):
    settings.MOYASAR_SECRET_KEY = ""
    with pytest.raises(NotImplementedError):
        LivePaymentsClient().fetch("x")


def test_live_client_calls_moyasar(settings):
    settings.MOYASAR_SECRET_KEY = "sk_test_123"
    with patch("urllib.request.urlopen") as urlopen:
        urlopen.return_value = _fake_response({"id": "inv_9", "url": "https://pay/inv_9"})
        checkout = LivePaymentsClient().create_checkout(
            amount_halalas=10000, description="d", return_url="https://r", metadata={"p": 1}
        )
        request = urlopen.call_args.args[0]
        assert request.full_url == "https://api.moyasar.com/v1/invoices"
        assert json.loads(request.data)["amount"] == 10000
        assert request.get_header("Authorization").startswith("Basic ")
        assert (checkout.ref, checkout.url) == ("inv_9", "https://pay/inv_9")

        for moyasar, ours in [("paid", "paid"), ("expired", "failed"), ("initiated", "pending")]:
            urlopen.return_value = _fake_response(
                {"status": moyasar, "amount": 10000, "currency": "sar"}
            )
            result = LivePaymentsClient().fetch("inv_9")
            assert (result.status, result.currency) == (ours, "SAR")


def test_halalas_to_sar():
    assert halalas_to_sar(10000) == "100.00"
    assert halalas_to_sar(1304) == "13.04"
    assert halalas_to_sar(5) == "0.05"
    assert halalas_to_sar(-150) == "-1.50"


def _data():
    return InvoiceData(
        number="INV-2026-000001",
        uuid="u",
        issued_at=datetime(2026, 11, 8, 18, 30, tzinfo=UTC),
        seller_name="منصة",
        seller_vat_number="300000000000003",
        total_halalas=10000,
        vat_halalas=1304,
    )


def test_qr_tlv_round_trip():
    fields = parse_qr_tlv(build_qr_tlv(_data()))
    assert fields == {
        1: "منصة",
        2: "300000000000003",
        3: "2026-11-08T18:30:00+00:00",
        4: "100.00",
        5: "13.04",
    }


def test_mock_zatca_reports():
    result = MockZatcaClient().report_simplified(_data())
    assert result.status == "reported"
    assert result.invoice_hash
    assert parse_qr_tlv(result.qr_base64)[4] == "100.00"


def test_live_zatca_not_ready():
    with pytest.raises(NotImplementedError):
        LiveZatcaClient().report_simplified(_data())
