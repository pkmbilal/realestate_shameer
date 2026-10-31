from .base import NafathClient, NafathRequest, NafathStatus


class LiveNafathClient(NafathClient):
    """Real Nafath API (settings.NAFATH_*). Written once the integration route is agreed
    (direct with the National Information Center, or through an approved provider)."""

    def _not_ready(self):
        raise NotImplementedError(
            "Nafath access is not set up yet. Use INTEGRATIONS_MODE=mock until "
            "the live client is added in integrations/nafath/live.py."
        )

    def start(self, national_id: str) -> NafathRequest:
        self._not_ready()

    def status(self, transaction_ref: str) -> NafathStatus:
        self._not_ready()
