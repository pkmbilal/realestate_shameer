"""Wallet business logic. The only code that writes CreditTransaction rows.

Every change locks the wallet row (select_for_update) inside transaction.atomic(), adds one
ledger row and updates the cached balance, so two requests can never spend the same credits.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.accounts.models import User
from apps.brokers.models import Agency, BrokerProfile

from .models import CreditPrice, CreditTransaction, Wallet

logger = logging.getLogger(__name__)
Kind = CreditTransaction.Kind
Action = CreditTransaction.Action


class WalletError(Exception):
    """A problem the user can see. `code` is a stable key the frontend translates."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# --- Finding wallets ---------------------------------------------------------------


def _get_or_create(*, broker: BrokerProfile | None = None, agency: Agency | None = None) -> Wallet:
    lookup = {"broker": broker} if broker is not None else {"agency": agency}
    try:
        with transaction.atomic():
            wallet, _ = Wallet.objects.get_or_create(**lookup)
    except IntegrityError:
        # Another request created it at the same moment.
        wallet = Wallet.objects.get(**lookup)
    return wallet


def wallet_for_user(user: User) -> Wallet | None:
    """The wallet a broker or agency admin spends from. Owners and buyers have none."""
    if user.role == User.Role.AGENCY_ADMIN:
        agency = Agency.objects.filter(admin=user).first()
        return _get_or_create(agency=agency) if agency else None
    if user.role == User.Role.BROKER:
        broker = BrokerProfile.objects.filter(user=user).first()
        return _get_or_create(broker=broker) if broker else None
    return None


def wallet_for_listing(listing) -> Wallet | None:
    """Who pays for a listing: its broker, else its agency. Owner listings are free (None).

    Agency members sharing the agency wallet is phase 2; for now a broker pays from their own.
    """
    if listing.broker_id:
        return _get_or_create(broker=listing.broker)
    if listing.agency_id:
        return _get_or_create(agency=listing.agency)
    return None


def price_for(action: str) -> CreditPrice:
    price, _ = CreditPrice.objects.get_or_create(action=action)
    return price


def current_prices() -> list[CreditPrice]:
    return [price_for(action) for action in Action.values]


# --- Writing the ledger --------------------------------------------------------------


def _add_entry(
    wallet: Wallet,
    amount: int,
    kind: str,
    *,
    action: str = "",
    listing=None,
    reverses: CreditTransaction | None = None,
    note: str = "",
    by: User | None = None,
) -> CreditTransaction:
    if not isinstance(amount, int) or isinstance(amount, bool) or amount == 0:
        raise WalletError("invalid_amount")
    with transaction.atomic():
        locked = Wallet.objects.select_for_update().get(pk=wallet.pk)
        new_balance = locked.balance + amount
        if new_balance < 0:
            raise WalletError("insufficient_credits")
        entry = CreditTransaction.objects.create(
            wallet=locked,
            kind=kind,
            action=action,
            amount=amount,
            balance_after=new_balance,
            listing=listing,
            reverses=reverses,
            note=note[:500],
            created_by=by,
        )
        locked.balance = new_balance
        locked.save(update_fields=["balance", "updated_at"])
    wallet.balance = new_balance
    logger.info("wallet %s %s %+d -> %s", wallet.pk, kind, amount, new_balance)
    return entry


def _require_note(note: str) -> str:
    note = (note or "").strip()
    if not note:
        raise WalletError("note_required")
    return note


def grant(wallet: Wallet, credits: int, by: User, note: str) -> CreditTransaction:
    """Free credits from staff, e.g. the launch promotion."""
    if not isinstance(credits, int) or credits <= 0:
        raise WalletError("invalid_amount")
    return _add_entry(wallet, credits, Kind.GRANT, note=_require_note(note), by=by)


def adjust(wallet: Wallet, amount: int, by: User, note: str) -> CreditTransaction:
    """A staff correction (positive or negative). The note explains why."""
    return _add_entry(wallet, amount, Kind.ADJUSTMENT, note=_require_note(note), by=by)


def charge(wallet: Wallet, action: str, *, listing=None, by: User | None = None):
    """Take the current price of `action`. Returns the ledger row, or None if it is free."""
    if action not in Action.values:
        raise WalletError("invalid_action")
    credits = price_for(action).credits
    if credits == 0:
        return None
    return _add_entry(wallet, -credits, Kind.SPEND, action=action, listing=listing, by=by)


def refund(entry: CreditTransaction, by: User | None = None, note: str = "") -> CreditTransaction:
    """Give back a spend in full. A spend can be refunded only once."""
    if entry.kind != Kind.SPEND:
        raise WalletError("not_refundable")
    try:
        with transaction.atomic():
            # Lock the wallet first so two refunds of the same spend queue up.
            Wallet.objects.select_for_update().get(pk=entry.wallet_id)
            if CreditTransaction.objects.filter(reverses=entry).exists():
                raise WalletError("already_refunded")
            return _add_entry(
                entry.wallet,
                -entry.amount,
                Kind.REFUND,
                action=entry.action,
                listing=entry.listing,
                reverses=entry,
                note=note,
                by=by,
            )
    except IntegrityError:
        raise WalletError("already_refunded") from None


# --- Checks ------------------------------------------------------------------------


def ledger_balance(wallet: Wallet) -> int:
    return wallet.transactions.aggregate(total=Sum("amount"))["total"] or 0


def balance_matches_ledger(wallet: Wallet) -> bool:
    wallet.refresh_from_db(fields=["balance"])
    return wallet.balance == ledger_balance(wallet)
