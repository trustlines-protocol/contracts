#! pytest
import pytest

from tests.conftest import (
    MAX_UINT_64,
)


@pytest.mark.parametrize("transfer", [10, -10, MAX_UINT_64, -MAX_UINT_64])
def test_open_trustline_with_transfer(
    currency_network_v2_adapter, accounts, transfer, web3
):
    creditor = accounts[0]
    debtor = accounts[1]
    credit_limit_given = 50
    credit_limit_received = 100
    latest_block = web3.eth.blockNumber

    currency_network_v2_adapter.update_trustline(
        creditor,
        debtor,
        creditline_given=credit_limit_given,
        creditline_received=credit_limit_received,
        transfer=transfer,
        accept=True,
    )
    assert currency_network_v2_adapter.check_account(
        creditor,
        debtor,
        creditline_given=credit_limit_given,
        creditline_received=credit_limit_received,
        balance=-transfer,
    )

    trustline_updates = currency_network_v2_adapter.events(
        "TrustlineUpdate", from_block=latest_block
    )
    assert len(trustline_updates) == 1
    trustline_update_args = trustline_updates[0]["args"]
    assert trustline_update_args["_creditor"] == creditor
    assert trustline_update_args["_debtor"] == debtor

    balance_updates = currency_network_v2_adapter.events(
        "BalanceUpdate", from_block=latest_block
    )
    assert len(balance_updates) == 1
    balance_update = balance_updates[0]["args"]

    transfer_events = currency_network_v2_adapter.events(
        "Transfer", from_block=latest_block
    )
    assert len(transfer_events) == 1
    transfer_args = transfer_events[0]["args"]

    if transfer > 0:
        assert balance_update["_value"] == -transfer
        assert balance_update["_from"] == creditor
        assert balance_update["_to"] == debtor
        assert transfer_args["_value"] == transfer
        assert transfer_args["_from"] == creditor
        assert transfer_args["_to"] == debtor
    else:
        assert balance_update["_value"] == transfer
        assert balance_update["_from"] == debtor
        assert balance_update["_to"] == creditor
        assert transfer_args["_value"] == -transfer
        assert transfer_args["_from"] == debtor
        assert transfer_args["_to"] == creditor


@pytest.mark.parametrize("transfer", [10, -10])
def test_trustline_request_event_with_transfer(
    currency_network_v2_adapter, accounts, web3, transfer
):
    creditor = accounts[0]
    debtor = accounts[1]
    credit_limit_given = 50
    credit_limit_received = 100
    latest_block = web3.eth.blockNumber

    currency_network_v2_adapter.update_trustline(
        creditor,
        debtor,
        creditline_given=credit_limit_given,
        creditline_received=credit_limit_received,
        transfer=transfer,
    )

    events = currency_network_v2_adapter.events(
        "TrustlineUpdateRequest", from_block=latest_block
    )
    assert len(events) == 1
    event_args = events[0]["args"]
    assert event_args["_transfer"] == transfer
    assert event_args["_creditor"] == creditor
    assert event_args["_debtor"] == debtor


def test_update_trustline_with_transfer(currency_network_v2_adapter, accounts):
    """Test that updating an already existing trustline with a transfer fails"""
    creditor = accounts[0]
    debtor = accounts[1]

    currency_network_v2_adapter.update_trustline(
        creditor, debtor, creditline_given=50, creditline_received=100, accept=True
    )

    currency_network_v2_adapter.update_trustline(
        creditor,
        debtor,
        creditline_given=50,
        creditline_received=100,
        transfer=10,
        should_fail=True,
    )


@pytest.mark.parametrize("transfer", [10, 0, -10])
def test_update_trustline_request_transfer_initiator(
    currency_network_v2_adapter, accounts, transfer
):
    """Test that the initiator of the trustline request can update the trustline request transfer"""
    creditor = accounts[0]
    debtor = accounts[1]
    initial_transfer = 100

    currency_network_v2_adapter.update_trustline(
        creditor,
        debtor,
        creditline_given=50,
        creditline_received=100,
        transfer=initial_transfer,
    )
    currency_network_v2_adapter.update_trustline(
        creditor,
        debtor,
        creditline_given=50,
        creditline_received=100,
        transfer=transfer,
    )

    assert currency_network_v2_adapter.check_account(
        creditor, debtor, creditline_given=0, creditline_received=0, balance=0
    )

    events = currency_network_v2_adapter.events("TrustlineUpdateRequest")
    assert len(events) == 2
    event_args = events[1]["args"]
    assert event_args["_transfer"] == transfer
    assert event_args["_creditor"] == creditor
    assert event_args["_debtor"] == debtor


@pytest.mark.parametrize("transfer", [10, 0, -10])
def test_update_trustline_request_transfer_counterparty(
    currency_network_v2_adapter, accounts, transfer
):
    """Test that the counterparty of the trustline request can update the trustline request transfer"""
    creditor = accounts[0]
    debtor = accounts[1]
    intital_transfer = 100

    currency_network_v2_adapter.update_trustline(
        creditor,
        debtor,
        creditline_given=50,
        creditline_received=100,
        transfer=intital_transfer,
    )
    currency_network_v2_adapter.update_trustline(
        debtor,
        creditor,
        creditline_given=50,
        creditline_received=100,
        transfer=transfer,
    )

    assert currency_network_v2_adapter.check_account(
        creditor, debtor, creditline_given=0, creditline_received=0, balance=0
    )

    events = currency_network_v2_adapter.events("TrustlineUpdateRequest")
    assert len(events) == 2
    event_args = events[1]["args"]
    assert event_args["_transfer"] == transfer
    assert event_args["_creditor"] == debtor
    assert event_args["_debtor"] == creditor


@pytest.mark.parametrize("balance", [MAX_UINT_64 + 1, -(MAX_UINT_64 + 1)])
def test_open_trustline_overflow_balance(
    currency_network_v2_adapter, accounts, balance
):
    """Test that trying to open a trustline with transfer out of bound fails"""
    creditor = accounts[0]
    debtor = accounts[1]
    credit_limit_given = 50
    credit_limit_received = 100

    currency_network_v2_adapter.update_trustline(
        creditor,
        debtor,
        creditline_given=credit_limit_given,
        creditline_received=credit_limit_received,
        transfer=balance,
        should_fail=True,
    )
