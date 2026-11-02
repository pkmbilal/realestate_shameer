from .base import RegaAdLicence, RegaClient


class LiveRegaClient(RegaClient):
    """Real REGA platform API (settings.REGA_*). Written once REGA shares the API
    specification and access credentials (open question in CLAUDE.md §11)."""

    def fetch_ad_licence(self, licence_number: str) -> RegaAdLicence:
        raise NotImplementedError(
            "REGA access is not set up yet. Use INTEGRATIONS_MODE=mock until "
            "the live client is added in integrations/rega/live.py."
        )
