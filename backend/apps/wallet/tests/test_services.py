import threading

import pytest
from django.db import connection

from apps.accounts.models import User
from apps.brokers.tests.factories import AgencyFactory, BrokerProfileFactory, VerifiedUserFactory
from apps.wallet import services
from apps.wallet.models import AppendOnlyError, CreditTransaction, Wallet

pytestmark = pytest.mark.django_db
Kind = CreditTransaction.Kind
Action = CreditTransaction.Action


def error_code(fn, *args, **kwargs):
    with pytest.raises(services.WalletError) as exc:
        fn(*args, **kwargs)
    return exc.value.code


# --- Finding wallets -----------------------------------------------------------------


def test_broker_and_agency_admin_get_one_wallet_each():
    broker = BrokerProfileFactory()
    agency = AgencyFactory()
    wallet = services.wallet_for_user(broker.user)
    assert wallet.broker == broker
    assert services.wallet_for_user(broker.user).pk == wallet.pk  # same one again
    assert services.wallet_for_user(agency.admin).agency == agency
    assert Wallet.objects.count() == 2


@pytest.mark.parametrize("role", [User.Role.OWNER, User.Role.BUYER, User.Role.BROKER])
def test_no_wallet_without_a_broker_or_agency_profile(role):
    assert services.wallet_for_user(VerifiedUserFactory(role=role)) is None


def test_current_prices_lists_every_action():
    assert [p.action for p in services.current_prices()] == Action.values


# --- Ledger ---------------------------------------------------------------------------


def test_grant_adds_credits_and_logs_it(broker, staff):
    wallet = services.wallet_for_user(broker.user)
    entry = services.grant(wallet, 50, staff, "Launch promotion")
    assert wallet.balance == 50
    assert entry.kind == Kind.GRANT
    assert entry.amount == 50
    assert entry.balance_after == 50
    assert entry.created_by == staff
    assert services.balance_matches_ledger(wallet)


@pytest.mark.parametrize("credits", [0, -5, "10", 1.5, True])
def test_grant_needs_a_positive_whole_number(broker, staff, credits):
    wallet = services.wallet_for_user(broker.user)
    assert error_code(services.grant, wallet, credits, staff, "x") == "invalid_amount"


def test_grant_and_adjust_need_a_note(funded_wallet, staff):
    assert error_code(services.grant, funded_wallet, 5, staff, "  ") == "note_required"
    assert error_code(services.adjust, funded_wallet, -5, staff, "") == "note_required"


def test_adjust_can_add_or_remove_but_not_overdraw(funded_wallet, staff):
    services.adjust(funded_wallet, -30, staff, "Duplicate grant")
    services.adjust(funded_wallet, 5, staff, "Goodwill")
    assert funded_wallet.balance == 75
    assert error_code(services.adjust, funded_wallet, -76, staff, "x") == "insufficient_credits"
    assert error_code(services.adjust, funded_wallet, 0, staff, "x") == "invalid_amount"
    assert services.balance_matches_ledger(funded_wallet)


def test_charge_takes_the_current_price(funded_wallet, set_price):
    set_price(Action.REFRESH, 15)
    entry = services.charge(funded_wallet, Action.REFRESH)
    assert entry.kind == Kind.SPEND
    assert entry.amount == -15
    assert funded_wallet.balance == 85
    assert services.balance_matches_ledger(funded_wallet)


def test_free_action_writes_nothing(funded_wallet):
    assert services.charge(funded_wallet, Action.POST) is None
    assert funded_wallet.transactions.count() == 1  # just the grant


def test_charge_refuses_overdraft_and_leaves_balance(funded_wallet, set_price):
    set_price(Action.FEATURE, 101)
    assert error_code(services.charge, funded_wallet, Action.FEATURE) == "insufficient_credits"
    funded_wallet.refresh_from_db()
    assert funded_wallet.balance == 100
    assert funded_wallet.transactions.count() == 1


def test_charge_unknown_action(funded_wallet):
    assert error_code(services.charge, funded_wallet, "boost") == "invalid_action"


def test_refund_returns_a_spend_once(funded_wallet, set_price, staff):
    set_price(Action.POST, 20)
    spend = services.charge(funded_wallet, Action.POST)
    refund = services.refund(spend, by=staff, note="rejected")
    assert refund.kind == Kind.REFUND
    assert refund.amount == 20
    assert refund.reverses == spend
    funded_wallet.refresh_from_db()
    assert funded_wallet.balance == 100
    assert error_code(services.refund, spend) == "already_refunded"
    assert services.balance_matches_ledger(funded_wallet)


def test_only_spends_can_be_refunded(funded_wallet):
    grant = funded_wallet.transactions.get()
    assert error_code(services.refund, grant) == "not_refundable"


def test_ledger_rows_cannot_be_changed_or_deleted(funded_wallet):
    entry = funded_wallet.transactions.get()
    entry.amount = 1_000
    with pytest.raises(AppendOnlyError):
        entry.save()
    with pytest.raises(AppendOnlyError):
        entry.delete()
    entry.refresh_from_db()
    assert entry.amount == 100


def test_balance_check_spots_a_tampered_cache(funded_wallet):
    Wallet.objects.filter(pk=funded_wallet.pk).update(balance=999)
    assert not services.balance_matches_ledger(funded_wallet)


@pytest.mark.django_db(transaction=True)
def test_parallel_charges_cannot_overspend(set_price, staff):
    """Two requests spending at the same moment: the row lock lets only one through."""
    wallet = services.wallet_for_user(BrokerProfileFactory().user)
    services.grant(wallet, 10, staff, "x")
    set_price(Action.FEATURE, 10)

    results = []
    barrier = threading.Barrier(2)

    def spend():
        barrier.wait()
        try:
            services.charge(Wallet.objects.get(pk=wallet.pk), Action.FEATURE)
            results.append("ok")
        except services.WalletError as exc:
            results.append(exc.code)
        finally:
            connection.close()

    threads = [threading.Thread(target=spend) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["insufficient_credits", "ok"]
    assert services.balance_matches_ledger(wallet)
    wallet.refresh_from_db()
    assert wallet.balance == 0
