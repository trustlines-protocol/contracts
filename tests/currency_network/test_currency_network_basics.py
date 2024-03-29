#! pytest
import attr
import pytest
from tldeploy.core import deploy_network

from tests.conftest import (
    EXTRA_DATA,
    EXPIRATION_TIME,
    MAX_UINT_64,
)
from tests.currency_network.conftest import (
    NETWORK_SETTING,
    trustlines,
    deploy_test_network,
)
from eth_tester.exceptions import TransactionFailed

MAX_CREDITLINE = MAX_UINT_64


@pytest.fixture(scope="session")
def currency_network_contract_with_trustline_update(web3, accounts):
    contract = deploy_network(
        web3, NETWORK_SETTING, currency_network_contract_name="CurrencyNetworkV2"
    )
    contract.functions.updateTrustline(accounts[1], 1, 1, 0, 0, False).transact(
        {"from": accounts[0]}
    )
    return contract


@pytest.fixture(scope="session", params=["+", "-"])
def invalid_interest_rate(request):
    max_interest_rate = 2000
    return int(request.param + str(max_interest_rate + 1))


def test_meta_name(currency_network_contract):
    assert currency_network_contract.functions.name().call() == "TestCoin"


def test_meta_symbol(currency_network_contract):
    assert currency_network_contract.functions.symbol().call() == "T"


def test_meta_decimal(currency_network_contract):
    assert currency_network_contract.functions.decimals().call() == 6


def test_init_only_once(currency_network_contract, assert_failing_transaction):
    assert_failing_transaction(
        currency_network_contract.functions.init(
            "TestCoin", "T", 6, 0, 0, False, False, EXPIRATION_TIME, []
        )
    )


def test_default_interests_rates_out_of_bounds(web3, invalid_interest_rate):
    invalid_settings = attr.evolve(
        NETWORK_SETTING, default_interest_rate=invalid_interest_rate
    )
    with pytest.raises(TransactionFailed):
        deploy_test_network(web3, invalid_settings)


def test_users(currency_network_contract_with_trustlines, accounts):
    A, B, C, D, E, *rest = accounts
    assert set(
        currency_network_contract_with_trustlines.functions.getUsers().call()
    ) == {A, B, C, D, E}


def test_friends(currency_network_contract_with_trustlines, accounts):
    A, B, C, D, E, *rest = accounts
    assert set(
        currency_network_contract_with_trustlines.functions.getFriends(A).call()
    ) == {B, E}


def test_set_get_Account(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest
    contract.functions.setAccount(
        accounts[0], accounts[1], 10, 20, 2, 3, False, 0, 4
    ).transact()
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [
        10,
        20,
        2,
        3,
        False,
        0,
        4,
    ]
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [
        20,
        10,
        3,
        2,
        False,
        0,
        -4,
    ]
    contract.functions.setAccount(
        accounts[1], accounts[0], 10, 20, 2, 3, False, 0, 4
    ).transact()
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [
        10,
        20,
        2,
        3,
        False,
        0,
        4,
    ]
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [
        20,
        10,
        3,
        2,
        False,
        0,
        -4,
    ]


def test_creditlines(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    for (A, B, clAB, clBA) in trustlines:
        assert contract.functions.creditline(accounts[A], accounts[B]).call() == clAB
        assert contract.functions.creditline(accounts[B], accounts[A]).call() == clBA
        assert contract.functions.balance(accounts[A], accounts[B]).call() == 0


def test_set_get_Account_default_interests(currency_network_contract, accounts):
    contract = currency_network_contract
    contract.functions.setAccountDefaultInterests(
        accounts[0], accounts[1], 10, 20, False, 0, 4
    ).transact()
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [
        10,
        20,
        0,
        0,
        False,
        0,
        4,
    ]
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [
        20,
        10,
        0,
        0,
        False,
        0,
        -4,
    ]
    contract.functions.setAccountDefaultInterests(
        accounts[1], accounts[0], 10, 20, False, 0, 4
    ).transact()
    assert contract.functions.getAccount(accounts[1], accounts[0]).call() == [
        10,
        20,
        0,
        0,
        False,
        0,
        4,
    ]
    assert contract.functions.getAccount(accounts[0], accounts[1]).call() == [
        20,
        10,
        0,
        0,
        False,
        0,
        -4,
    ]


def test_balance(currency_network_contract, accounts, make_currency_network_adapter):
    contract = currency_network_contract
    currency_network_adapter = make_currency_network_adapter(currency_network_contract)

    currency_network_adapter.set_account(
        accounts[0], accounts[1], creditline_given=10, creditline_received=20, balance=4
    )
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 4
    assert contract.functions.balance(accounts[1], accounts[0]).call() == -4


def test_transfer_0_mediators(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, *rest = accounts
    currency_network_adapter.transfer(110, path=[A, B])
    assert currency_network_adapter.balance(A, B) == -110


def test_transfer_0_mediators_fail_not_enough_credit(
    currency_network_adapter_with_trustlines, accounts
):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, *rest = accounts
    currency_network_adapter.transfer(151, path=[A, B], should_fail=True)


def test_transfer_0_mediators_fail_wrong_path(
    currency_network_contract_with_trustlines, accounts, assert_failing_transaction
):
    contract = currency_network_contract_with_trustlines
    assert_failing_transaction(
        contract.functions.transfer(110, 0, [accounts[0], accounts[2]], EXTRA_DATA),
        {"from": accounts[0]},
    )
    assert_failing_transaction(
        contract.functions.transfer(1, 0, [accounts[2], accounts[1]], EXTRA_DATA),
        {"from": accounts[0]},
    )


def test_transfer_1_mediators(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, C, *rest = accounts
    currency_network_adapter.transfer(110, path=[A, B, C])

    assert currency_network_adapter.balance(A, B) == -110
    assert currency_network_adapter.balance(C, B) == 110


def test_transfer_1_mediators_not_enough_credit(
    currency_network_adapter_with_trustlines, accounts
):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, C, *rest = accounts

    currency_network_adapter.transfer(151, path=[A, B, C], should_fail=True)


def test_transfer_1_mediators_not_enough_wrong_path(
    currency_network_adapter_with_trustlines, accounts
):
    currency_network_adapter_with_trustlines.transfer(
        value=110, path=[accounts[0], accounts[1], accounts[3]], should_fail=True
    )


def test_transfer_3_mediators(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, C, D, E, *rest = accounts

    currency_network_adapter.transfer(110, path=[A, B, C, D, E])

    assert currency_network_adapter.balance(A, B) == -110
    assert currency_network_adapter.balance(B, C) == -110
    assert currency_network_adapter.balance(C, D) == -110
    assert currency_network_adapter.balance(E, D) == 110


def test_transfer_payback(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, C, D, E, *rest = accounts

    currency_network_adapter.transfer(110, path=[A, B, C, D, E])
    currency_network_adapter.transfer(110, path=[E, D, C, B, A])

    assert currency_network_adapter.balance(A, B) == 0
    assert currency_network_adapter.balance(B, C) == 0
    assert currency_network_adapter.balance(C, D) == 0
    assert currency_network_adapter.balance(E, D) == 0


def test_send_back(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, *rest = accounts

    assert currency_network_adapter.balance(A, B) == 0

    currency_network_adapter.transfer(120, path=[A, B])
    assert currency_network_adapter.balance(B, A) == 120

    currency_network_adapter.transfer(120, path=[B, A])
    assert currency_network_adapter.balance(A, B) == 0


def test_send_more(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, *rest = accounts

    assert currency_network_adapter.balance(A, B) == 0
    currency_network_adapter.transfer(120, path=[A, B])
    assert currency_network_adapter.balance(B, A) == 120
    currency_network_adapter.transfer(200, path=[B, A])
    assert currency_network_adapter.balance(A, B) == 80


def test_can_always_reduce(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter_with_trustlines.transfer(
        120, path=[accounts[0], accounts[1]]
    )
    assert (
        currency_network_adapter_with_trustlines.balance(accounts[1], accounts[0])
        == 120
    )

    # reduce creditlimits below balance
    currency_network_adapter_with_trustlines.update_trustline(
        accounts[0], accounts[1], creditline_given=0, creditline_received=0
    )
    assert (
        currency_network_adapter_with_trustlines.contract.functions.creditline(
            accounts[1], accounts[0]
        ).call()
        == 0
    )
    assert (
        currency_network_adapter_with_trustlines.contract.functions.creditline(
            accounts[0], accounts[1]
        ).call()
        == 0
    )

    currency_network_adapter_with_trustlines.transfer(
        50, path=[accounts[1], accounts[0]]
    )
    assert (
        currency_network_adapter_with_trustlines.balance(accounts[1], accounts[0]) == 70
    )


def test_update_cannot_open_zero_trustline(currency_network_adapter, accounts):
    A, C, *rest = accounts

    currency_network_adapter.update_trustline(
        A, C, creditline_given=0, creditline_received=0, should_fail=True
    )

    assert currency_network_adapter.events("TrustlineUpdate") == []


def test_update_without_accept_trustline(currency_network_adapter, accounts):
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100
    )
    assert currency_network_adapter.creditline(A, B) == 0
    assert currency_network_adapter.creditline(B, A) == 0

    assert currency_network_adapter.events("TrustlineUpdate") == []
    assert (
        currency_network_adapter.events("TrustlineUpdateRequest")[0]["args"][
            "_creditlineGiven"
        ]
        == 50
    )


def test_update_with_accept_trustline(currency_network_adapter, accounts):
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100
    )
    currency_network_adapter.update_trustline(
        B, A, creditline_given=100, creditline_received=50
    )

    assert currency_network_adapter.creditline(A, B) == 50
    assert currency_network_adapter.creditline(B, A) == 100

    assert (
        currency_network_adapter.events("TrustlineUpdate")[0]["args"]["_creditor"] == A
    )
    assert (
        currency_network_adapter.events("TrustlineUpdate")[0]["args"][
            "_creditlineGiven"
        ]
        == 50
    )


def test_update_with_accept_lower_trustline(currency_network_adapter, accounts):
    A, B, *rest = accounts
    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100
    )
    currency_network_adapter.update_trustline(
        B, A, creditline_given=100, creditline_received=49
    )
    # this was changed so it will accept the lower common ground
    assert currency_network_adapter.creditline(A, B) == 49
    assert currency_network_adapter.creditline(B, A) == 100
    assert (
        currency_network_adapter.events("TrustlineUpdate")[0]["args"]["_creditor"] == A
    )
    assert (
        currency_network_adapter.events("TrustlineUpdate")[0]["args"][
            "_creditlineGiven"
        ]
        == 49
    )


def test_update_with_accept_higher_trustline(currency_network_adapter, accounts):
    A, B, *rest = accounts
    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100
    )
    currency_network_adapter.update_trustline(
        B, A, creditline_given=100, creditline_received=51
    )

    assert currency_network_adapter.creditline(A, B) == 0
    assert currency_network_adapter.creditline(B, A) == 0
    assert currency_network_adapter.events("TrustlineUpdate") == []


def test_update_with_accept_2nd_trustline(currency_network_adapter, accounts):
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100
    )
    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=99
    )
    currency_network_adapter.update_trustline(
        B, A, creditline_given=99, creditline_received=50
    )
    assert currency_network_adapter.creditline(A, B) == 50
    assert currency_network_adapter.creditline(B, A) == 99
    assert (
        currency_network_adapter.events("TrustlineUpdate")[0]["args"]["_creditor"] == A
    )
    assert (
        currency_network_adapter.events("TrustlineUpdate")[0]["args"][
            "_creditlineGiven"
        ]
        == 50
    )


def test_cannot_accept_old_trustline(currency_network_adapter, accounts):
    A, B, *rest = accounts
    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100
    )
    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=99
    )
    currency_network_adapter.update_trustline(
        B, A, creditline_given=100, creditline_received=50
    )
    assert currency_network_adapter.creditline(A, B) == 0
    assert currency_network_adapter.creditline(B, A) == 0
    assert currency_network_adapter.events("TrustlineUpdate") == []


@pytest.mark.parametrize(
    "new_creditlimit_given, new_creditlmit_received", [(99, 150), (0, 0)]
)
def test_update_reduce_need_no_accept_trustline(
    web3,
    currency_network_adapter_with_trustlines,
    accounts,
    new_creditlimit_given,
    new_creditlmit_received,
):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, *rest = accounts

    assert currency_network_adapter.creditline(A, B) == 100
    assert currency_network_adapter.creditline(B, A) == 150

    currency_network_adapter.update_trustline(
        A,
        B,
        creditline_given=new_creditlimit_given,
        creditline_received=new_creditlmit_received,
    )
    assert currency_network_adapter.creditline(A, B) == new_creditlimit_given
    assert currency_network_adapter.creditline(B, A) == new_creditlmit_received
    assert (
        currency_network_adapter.events(
            "TrustlineUpdate", from_block=web3.eth.blockNumber
        )[0]["args"]["_creditlineGiven"]
        == new_creditlimit_given
    )


def test_update_without_accept_trustline_interests(
    currency_network_adapter_custom_interest, accounts
):
    currency_network_adapter = currency_network_adapter_custom_interest
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100, interest_rate_given=1
    )

    assert currency_network_adapter.interest_rate(A, B) == 0
    assert currency_network_adapter.interest_rate(B, A) == 0

    assert currency_network_adapter.events("TrustlineUpdate") == []
    assert (
        currency_network_adapter.events("TrustlineUpdateRequest")[0]["args"][
            "_interestRateGiven"
        ]
        == 1
    )


def test_update_with_accept_trustline_interests(
    currency_network_adapter_custom_interest, accounts
):
    currency_network_adapter = currency_network_adapter_custom_interest

    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=100, interest_rate_given=1
    )
    currency_network_adapter.update_trustline(
        B, A, creditline_given=100, creditline_received=50, interest_rate_received=1
    )

    assert currency_network_adapter.interest_rate(A, B) == 1
    assert currency_network_adapter.interest_rate(B, A) == 0

    events = currency_network_adapter.events("TrustlineUpdate")
    assert events[0]["args"]["_creditor"] == A
    assert events[0]["args"]["_interestRateGiven"] == 1


def test_update_with_accept_different_trustline_interests(
    currency_network_contract_custom_interest, accounts
):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100, 1, 0, False).transact({"from": A})
    contract.functions.updateTrustline(A, 100, 50, 0, 2, False).transact({"from": B})
    assert contract.functions.interestRate(A, B).call() == 0
    assert contract.functions.interestRate(B, A).call() == 0
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()
        == []
    )


def test_update_with_accept_2nd_trustline_interests(
    currency_network_contract_custom_interest, accounts
):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100, 2, 0, False).transact({"from": A})
    contract.functions.updateTrustline(B, 50, 100, 1, 0, False).transact({"from": A})
    contract.functions.updateTrustline(A, 100, 50, 0, 1, False).transact({"from": B})
    assert contract.functions.interestRate(A, B).call() == 1
    assert contract.functions.interestRate(B, A).call() == 0
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_creditor"]
        == A
    )
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()[0][
            "args"
        ]["_interestRateGiven"]
        == 1
    )


def test_cannot_accept_old_trustline_interests(
    currency_network_contract_custom_interest, accounts
):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100, 2, 0, False).transact({"from": A})
    contract.functions.updateTrustline(B, 50, 100, 1, 0, False).transact({"from": A})
    contract.functions.updateTrustline(A, 100, 50, 0, 2, False).transact({"from": B})
    assert contract.functions.interestRate(A, B).call() == 0
    assert contract.functions.interestRate(B, A).call() == 0
    assert (
        contract.events.TrustlineUpdate.createFilter(fromBlock=0).get_all_entries()
        == []
    )


def test_cannot_accept_trustline_request_after_reduce(
    currency_network_contract_custom_interest, accounts
):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 50, 100, 0, 0, False).transact(
        {"from": A}
    )  # Propose trustline
    contract.functions.updateTrustline(A, 100, 50, 0, 0, False).transact(
        {"from": B}
    )  # Accept trustline
    contract.functions.updateTrustline(B, 10, 20, 0, 0, False).transact(
        {"from": A}
    )  # Lower trustline
    contract.functions.updateTrustline(A, 100, 50, 0, 0, False).transact(
        {"from": B}
    )  # Try to accept old trustline
    assert contract.functions.creditline(A, B).call() == 10
    assert contract.functions.creditline(B, A).call() == 20


def test_update_trustline_with_custom_while_forbidden(
    currency_network_adapter, accounts
):
    """Verifies that if the network uses default interests of 0, no custom interests can be put"""

    A, B, *rest = accounts
    currency_network_adapter.update_trustline(
        A, B, interest_rate_given=2, interest_rate_received=1, should_fail=True
    )


def test_update_trustline_with_custom_while_forbidden_lowering_interests(
    currency_network_adapter, accounts
):
    """Verifies that if the network uses default interests of 0, no custom interests can be put"""
    currency_network_adapter.contract.functions.setNetworkSettings(
        "TestCoin", "T", 6, 0, 5, False, False
    ).transact()

    A, B, *rest = accounts
    currency_network_adapter.contract.functions.setAccountDefaultInterests(
        A, B, 200, 200, False, 0, 0
    ).transact()

    currency_network_adapter.update_trustline(
        A, B, interest_rate_given=1, interest_rate_received=1, should_fail=True
    )


def test_update_trustline_lowering_interest_given(currency_network_adapter, accounts):
    """Verifies that one can update a trustline by lowering interests rate given without agreement of debtor"""
    currency_network_adapter.contract.functions.setNetworkSettings(
        "TestCoin", "T", 6, 0, 0, True, False
    ).transact()

    A, B, *rest = accounts
    currency_network_adapter.update_trustline(A, B, interest_rate_received=2)
    currency_network_adapter.update_trustline(B, A, interest_rate_given=1)

    assert currency_network_adapter.interest_rate(B, A) == 1


def test_update_trustline_lowering_interest_received(
    currency_network_adapter, accounts
):
    """Verifies that one can not update a trustline by lowering interests rate received without agreement of debtor"""
    currency_network_adapter.contract.functions.setNetworkSettings(
        "TestCoin", "T", 6, 0, 0, True, False
    ).transact()

    A, B, *rest = accounts
    currency_network_adapter.update_trustline(A, B, interest_rate_given=2)
    currency_network_adapter.update_trustline(B, A, interest_rate_received=1)

    assert currency_network_adapter.interest_rate(B, A) == 0
    assert currency_network_adapter.events("TrustlineUpdate") == []


def test_setting_trustline_with_negative_interests_with_custom_interests(
    currency_network_adapter_with_trustlines, accounts
):
    """Verifies we cannot use negative interests if the flag for custom is set"""
    currency_network_adapter = currency_network_adapter_with_trustlines
    currency_network_adapter.contract.functions.setNetworkSettings(
        "TestCoin", "T", 6, 0, 0, True, False
    ).transact()
    A, B, *rest = accounts

    currency_network_adapter.set_account(
        A, B, interest_rate_given=-1000, interest_rate_received=-1000, should_fail=True
    )

    currency_network_adapter.update_trustline(
        A, B, interest_rate_given=-2, should_fail=True
    )


@pytest.mark.parametrize(
    "interest_rate_param", ["interest_rate_given", "interest_rate_received"]
)
def test_update_trustline_interests_out_of_bounds(
    currency_network_adapter_custom_interest,
    interest_rate_param,
    accounts,
    invalid_interest_rate,
):
    currency_network_adapter = currency_network_adapter_custom_interest
    A, B, *rest = accounts

    param_dict = {interest_rate_param: invalid_interest_rate}

    currency_network_adapter.update_trustline(
        A,
        B,
        creditline_given=50,
        creditline_received=50,
        **param_dict,
        should_fail=True,
    )


def test_cancel_trustline_update(
    currency_network_contract_with_trustline_update,
    accounts,
    assert_failing_transaction,
):
    """Test that a trustline update is canceled when calling `cancelTrustlineUpdate`"""
    contract = currency_network_contract_with_trustline_update

    contract.functions.cancelTrustlineUpdate(accounts[1]).transact(
        {"from": accounts[0]}
    )

    # to test it we try to accept the update and make a transfer that should fail
    contract.functions.updateTrustline(accounts[0], 1, 1, 0, 0, False).transact(
        {"from": accounts[1]}
    )

    assert_failing_transaction(
        contract.functions.transfer(1, 1, [accounts[1], accounts[0]], EXTRA_DATA),
        {"from": accounts[1]},
    )


def test_cancel_trustline_update_not_initiator(
    currency_network_contract_with_trustline_update,
    accounts,
    assert_failing_transaction,
):
    """Test that a trustline update canceled while not initiator"""
    contract = currency_network_contract_with_trustline_update

    contract.functions.cancelTrustlineUpdate(accounts[0]).transact(
        {"from": accounts[1]}
    )

    # to test it we try to accept the update and make a transfer that should fail
    contract.functions.updateTrustline(accounts[1], 1, 1, 0, 0, False).transact(
        {"from": accounts[0]}
    )

    assert_failing_transaction(
        contract.functions.transfer(1, 1, [accounts[0], accounts[1]], EXTRA_DATA),
        {"from": accounts[0]},
    )


def test_cancel_no_trustline_update(
    currency_network_adapter,
    accounts,
):

    currency_network_adapter.cancel_trustline_update(
        accounts[1], accounts[0], should_fail=True
    )


def test_cancel_trustline_update_event(
    currency_network_contract_with_trustline_update, accounts
):
    contract = currency_network_contract_with_trustline_update

    contract.functions.cancelTrustlineUpdate(accounts[1]).transact(
        {"from": accounts[0]}
    )
    events = contract.events.TrustlineUpdateCancel.createFilter(
        fromBlock=0
    ).get_all_entries()
    event_args = events[0]["args"]

    assert len(events) == 1
    assert event_args["_initiator"] == accounts[0]
    assert event_args["_counterparty"] == accounts[1]


def test_balance_event(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, *rest = accounts

    currency_network_adapter.transfer(110, path=[A, B])
    events = currency_network_adapter.events("BalanceUpdate")
    assert len(events) == 1
    args = events[0]["args"]
    from_ = args["_from"]
    to = args["_to"]
    value = args["_value"]
    if from_ == A and to == B:
        assert value == -110
    elif from_ == B and to == A:
        assert value == 110
    else:
        assert (
            False
        ), "Wrong _from and _to in the event: were: {}, {}, but expected: {}, {}".format(
            from_, to, A, B
        )


def test_transfer_event(currency_network_adapter_with_trustlines, accounts):
    currency_network_adapter = currency_network_adapter_with_trustlines
    A, B, *rest = accounts

    currency_network_adapter.transfer(110, path=[A, B])
    events = currency_network_adapter.events("Transfer")
    assert len(events) == 1
    args = events[0]["args"]
    from_ = args["_from"]
    to = args["_to"]
    value = args["_value"]
    extra_data = args["_extraData"]
    assert from_ == A
    assert to == B
    assert value == 110
    assert extra_data == EXTRA_DATA


def test_update_trustline_add_users(currency_network_adapter, accounts):
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=50, creditline_received=50, accept=True
    )

    assert len(currency_network_adapter.contract.functions.getUsers().call()) == 2


def test_update_set_account_add_users(currency_network_adapter, accounts):
    A, B, *rest = accounts
    currency_network_adapter.set_account(
        A, B, creditline_given=50, creditline_received=100
    )
    assert len(currency_network_adapter.contract.functions.getUsers().call()) == 2


def test_max_transfer(currency_network_adapter, accounts):
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A,
        B,
        creditline_given=MAX_CREDITLINE,
        creditline_received=MAX_CREDITLINE,
        accept=True,
    )
    currency_network_adapter.transfer(MAX_CREDITLINE, path=[A, B])

    assert currency_network_adapter.balance(A, B) == -MAX_CREDITLINE


def test_overflow_max_transfer(currency_network_adapter, accounts):
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A,
        B,
        creditline_given=MAX_CREDITLINE,
        creditline_received=MAX_CREDITLINE,
        accept=True,
    )
    currency_network_adapter.transfer(MAX_CREDITLINE, path=[A, B])

    currency_network_adapter.transfer(1, path=[A, B], should_fail=True)


def test_transfer_no_path(
    currency_network_adapter, accounts, assert_failing_transaction
):
    assert_failing_transaction(
        currency_network_adapter.contract.functions.transfer(1, 100, [], EXTRA_DATA),
        {"from": accounts[0]},
    )


def test_transfer_too_short_path(currency_network_adapter, accounts):
    currency_network_adapter.transfer(1, path=[accounts[0]], should_fail=True)
