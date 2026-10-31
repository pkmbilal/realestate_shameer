from .base import SmsClient


class LiveSmsClient(SmsClient):
    """Real SMS provider. Written once the owner signs with Unifonic or Taqnyat."""

    def send(self, phone: str, text: str) -> None:
        raise NotImplementedError(
            "No SMS provider is configured yet. Use INTEGRATIONS_MODE=mock until "
            "the Unifonic/Taqnyat client is added in integrations/sms/live.py."
        )
