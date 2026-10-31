from abc import ABC, abstractmethod


class SmsClient(ABC):
    """Sends a plain-text SMS to one phone number (E.164)."""

    @abstractmethod
    def send(self, phone: str, text: str) -> None: ...
