from .base import InvoiceData, ZatcaClient, ZatcaResult


class LiveZatcaClient(ZatcaClient):
    """ZATCA Fatoora (Phase 2 integration).

    Not written yet: it needs ZATCA onboarding first (a compliance CSID and a production CSID
    for our EGS unit), then signed UBL XML invoices. Until then use INTEGRATIONS_MODE=mock.
    """

    def report_simplified(self, data: InvoiceData) -> ZatcaResult:
        raise NotImplementedError(
            "The live ZATCA client is not available until ZATCA onboarding (CSID) is done. "
            "Use INTEGRATIONS_MODE=mock."
        )
