from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class NafathStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class NafathRequest:
    transaction_ref: str
    # Shown on our site; the person taps the same number in the Nafath app to approve.
    random_number: str


class NafathClient(ABC):
    """Verifies a person's identity through the national Nafath app.

    The national ID is only passed through to Nafath; callers must never store or log it.
    """

    @abstractmethod
    def start(self, national_id: str) -> NafathRequest: ...

    @abstractmethod
    def status(self, transaction_ref: str) -> NafathStatus: ...
