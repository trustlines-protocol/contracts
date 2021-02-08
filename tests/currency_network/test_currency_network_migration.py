#! pytest

import pytest

from tests.conftest import (
    CurrencyNetworkAdapter,
    get_single_event_of_contract,
    get_events_of_contract,
)

ADDRESS_0 = "0x0000000000000000000000000000000000000000"


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def not_owner(accounts, owner):
    not_owner = accounts[1]
    assert not_owner != owner
    return not_owner


@pytest.fixture(scope="session")
def currency_network_contract(owned_currency_network):
    # This is just an alias
    return owned_currency_network


@pytest.fixture(scope="session")
def currency_network_adapter(currency_network_contract, make_currency_network_adapter):
    return make_currency_network_adapter(currency_network_contract)


def test_remove_owner(currency_network_contract, owner):
    currency_network_contract.functions.removeOwner().transact({"from": owner})
    assert currency_network_contract.functions.owner().call() == ADDRESS_0


def test_remover_owner_not_owner(currency_network_adapter, not_owner):
    currency_network_adapter.remove_owner(sender=not_owner, should_fail=True)


def test_remove_owner_event(currency_network_contract, owner, web3):
    currency_network_contract.functions.removeOwner().transact({"from": owner})
    assert (
        get_single_event_of_contract(
            currency_network_contract,
            "OwnerRemoval",
            web3.eth.blockNumber,
        )
        is not None
    )


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 2), (2, 1)])
def test_set_account(
    currency_network_adapter: CurrencyNetworkAdapter,
    owner,
    accounts,
    creditor_index,
    debtor_index,
    web3,
):
    creditor = accounts[creditor_index]
    debtor = accounts[debtor_index]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True
    old_mtime = 123456
    balance = 1000
    currency_network_adapter.contract.functions.setAccount(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        old_mtime,
        balance,
    ).transact({"from": owner})

    # Interests are applied when setting account for migration
    new_mtime = web3.eth.getBlock(web3.eth.blockNumber)["timestamp"]
    new_balance = currency_network_adapter.balance_with_interests(
        balance, old_mtime, new_mtime, interest_rate_given, interest_rate_received
    )

    assert currency_network_adapter.check_account(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        new_mtime,
        new_balance,
    )


def test_set_account_not_owner(
    currency_network_adapter: CurrencyNetworkAdapter, not_owner, accounts
):
    creditor = accounts[1]
    debtor = accounts[2]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True
    m_time = 123456
    balance = 1000

    currency_network_adapter.set_account(
        creditor,
        debtor,
        creditline_given=creditline_given,
        creditline_received=creditline_received,
        interest_rate_given=interest_rate_given,
        interest_rate_received=interest_rate_received,
        is_frozen=is_frozen,
        m_time=m_time,
        balance=balance,
        should_fail=True,
        transaction_options={"from": not_owner},
    )


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 2), (2, 1)])
def test_set_account_events(
    currency_network_adapter: CurrencyNetworkAdapter,
    owner,
    accounts,
    creditor_index,
    debtor_index,
    web3,
):
    creditor = accounts[creditor_index]
    debtor = accounts[debtor_index]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True
    old_mtime = 123456
    balance = 1000

    block_number = web3.eth.blockNumber
    currency_network_adapter.contract.functions.setAccount(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        old_mtime,
        balance,
    ).transact({"from": owner})

    new_mtime = web3.eth.getBlock(web3.eth.blockNumber)["timestamp"]
    new_balance = currency_network_adapter.balance_with_interests(
        balance, old_mtime, new_mtime, interest_rate_given, interest_rate_received
    )

    trustline_update_event_args = get_single_event_of_contract(
        currency_network_adapter.contract, "TrustlineUpdate", block_number
    )["args"]
    assert trustline_update_event_args["_creditor"] == creditor
    assert trustline_update_event_args["_debtor"] == debtor
    assert trustline_update_event_args["_creditlineGiven"] == creditline_given
    assert trustline_update_event_args["_creditlineReceived"] == creditline_received
    assert trustline_update_event_args["_interestRateGiven"] == interest_rate_given
    assert (
        trustline_update_event_args["_interestRateReceived"] == interest_rate_received
    )
    assert trustline_update_event_args["_isFrozen"] == is_frozen

    balance_update_event_args = get_single_event_of_contract(
        currency_network_adapter.contract, "BalanceUpdate", block_number
    )["args"]
    assert balance_update_event_args["_from"] == creditor
    assert balance_update_event_args["_to"] == debtor
    assert balance_update_event_args["_value"] == new_balance


def test_set_account_add_friends(
    currency_network_adapter: CurrencyNetworkAdapter, owner, accounts
):
    creditor = accounts[1]
    debtor = accounts[2]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True
    mtime = 123456
    balance = 1000

    creditor_friends_before = currency_network_adapter.contract.functions.getFriends(
        creditor
    ).call()
    debtor_friends_before = currency_network_adapter.contract.functions.getFriends(
        debtor
    ).call()

    currency_network_adapter.contract.functions.setAccount(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        mtime,
        balance,
    ).transact({"from": owner})

    creditor_friends_after = currency_network_adapter.contract.functions.getFriends(
        creditor
    ).call()
    debtor_friends_after = currency_network_adapter.contract.functions.getFriends(
        debtor
    ).call()

    creditor_added_friends = set(creditor_friends_after) - set(creditor_friends_before)
    debtor_added_friends = set(debtor_friends_after) - set(debtor_friends_before)

    assert len(creditor_added_friends) == 1
    assert len(debtor_added_friends) == 1
    assert creditor_added_friends.pop() == debtor
    assert debtor_added_friends.pop() == creditor


def test_set_account_add_users(
    currency_network_adapter: CurrencyNetworkAdapter, owner, accounts
):
    creditor = accounts[5]
    debtor = accounts[6]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True
    mtime = 123456
    balance = 1000

    users_before = currency_network_adapter.contract.functions.getUsers().call()
    assert creditor not in users_before
    assert debtor not in users_before

    currency_network_adapter.contract.functions.setAccount(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        mtime,
        balance,
    ).transact({"from": owner})

    users_after = currency_network_adapter.contract.functions.getUsers().call()

    new_users = set(users_after) - set(users_before)

    assert len(new_users) == 2
    assert creditor in new_users
    assert debtor in new_users


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 2), (2, 1)])
def test_set_trustline_request(
    currency_network_adapter: CurrencyNetworkAdapter,
    owner,
    accounts,
    creditor_index,
    debtor_index,
):
    creditor = accounts[creditor_index]
    debtor = accounts[debtor_index]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True

    currency_network_adapter.set_trustline_request(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        transaction_options={"from": owner},
    )

    # Check that the trustline request was successfully set by accepting it from the debtor
    currency_network_adapter.unfreeze_network(transaction_options={"from": owner})
    currency_network_adapter.update_trustline(
        creditor_address=debtor,
        debtor_address=creditor,
        creditline_given=creditline_received,
        creditline_received=creditline_given,
        interest_rate_given=interest_rate_received,
        interest_rate_received=interest_rate_given,
        is_frozen=is_frozen,
    )
    currency_network_adapter.check_account(
        a_address=creditor,
        b_address=debtor,
        creditline_given=creditline_given,
        creditline_received=creditline_received,
        interest_rate_given=interest_rate_given,
        interest_rate_received=interest_rate_received,
        is_frozen=is_frozen,
        balance=0,
    )


def test_set_trustline_request_not_owner(
    currency_network_adapter: CurrencyNetworkAdapter,
    not_owner,
    accounts,
):
    creditor = accounts[0]
    debtor = accounts[1]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True

    currency_network_adapter.set_trustline_request(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        transaction_options={"from": not_owner},
        should_fail=True,
    )


def test_set_trustline_request_event(
    currency_network_adapter: CurrencyNetworkAdapter, owner, accounts, web3
):
    creditor = accounts[0]
    debtor = accounts[1]
    creditline_given = 123
    creditline_received = 321
    interest_rate_given = 1
    interest_rate_received = 2
    is_frozen = True

    currency_network_adapter.set_trustline_request(
        creditor,
        debtor,
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        transaction_options={"from": owner},
    )
    trustline_update_request_event_args = get_single_event_of_contract(
        currency_network_adapter.contract,
        "TrustlineUpdateRequest",
        web3.eth.blockNumber,
    )["args"]

    assert trustline_update_request_event_args["_creditor"] == creditor
    assert trustline_update_request_event_args["_debtor"] == debtor
    assert trustline_update_request_event_args["_creditlineGiven"] == creditline_given
    assert (
        trustline_update_request_event_args["_creditlineReceived"]
        == creditline_received
    )
    assert (
        trustline_update_request_event_args["_interestRateGiven"] == interest_rate_given
    )
    assert (
        trustline_update_request_event_args["_interestRateReceived"]
        == interest_rate_received
    )
    assert trustline_update_request_event_args["_isFrozen"] == is_frozen


def test_set_on_boarder(currency_network_contract, owner, accounts):
    user = accounts[1]
    on_boarder = accounts[2]
    currency_network_contract.functions.setOnboarder(user, on_boarder).transact(
        {"from": owner}
    )
    assert currency_network_contract.functions.onboarder(user).call() == on_boarder


def test_set_on_boarder_not_owner(currency_network_adapter, not_owner, accounts):
    user = accounts[1]
    on_boarder = accounts[2]

    currency_network_adapter.set_on_boarder(
        user, on_boarder, transaction_options={"from": not_owner}, should_fail=True
    )


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 2), (2, 1)])
def test_set_on_boarder_event(
    currency_network_contract, owner, accounts, creditor_index, debtor_index, web3
):
    user = accounts[1]
    on_boarder = accounts[2]

    block_number = web3.eth.blockNumber
    currency_network_contract.functions.setOnboarder(user, on_boarder).transact(
        {"from": owner}
    )

    event_args = get_single_event_of_contract(
        currency_network_contract, "Onboard", block_number
    )["args"]
    assert event_args["_onboarder"] == on_boarder
    assert event_args["_onboardee"] == user


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 2), (2, 1)])
def test_set_debt(
    currency_network_contract, owner, accounts, creditor_index, debtor_index
):
    debtor = accounts[creditor_index]
    creditor = accounts[debtor_index]
    value = 123
    currency_network_contract.functions.setDebt(debtor, creditor, value).transact(
        {"from": owner}
    )
    assert currency_network_contract.functions.getDebt(debtor, creditor).call() == value


def test_set_debt_not_owner(currency_network_adapter, not_owner, accounts):
    currency_network_adapter.set_debt(
        accounts[1],
        accounts[2],
        123,
        transaction_options={"from": not_owner},
        should_fail=True,
    )


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 2), (2, 1)])
def test_set_debt_event(
    currency_network_contract, owner, accounts, creditor_index, debtor_index, web3
):
    debtor = accounts[creditor_index]
    creditor = accounts[debtor_index]
    value = 123
    block_number = web3.eth.blockNumber
    currency_network_contract.functions.setDebt(debtor, creditor, value).transact(
        {"from": owner}
    )
    events = get_events_of_contract(
        currency_network_contract, "DebtUpdate", block_number
    )
    assert len(events) == 1
    event_args = events[0]["args"]
    assert event_args["_debtor"] == debtor
    assert event_args["_creditor"] == creditor
    assert event_args["_newDebt"] == value


def test_network_starts_frozen(currency_network_contract):
    assert currency_network_contract.functions.isNetworkFrozen().call()


def test_unfreeze_network(currency_network_adapter, owner):
    currency_network_adapter.unfreeze_network(transaction_options={"from": owner})
    assert not currency_network_adapter.is_network_frozen()


def test_unfreeze_network_not_owner(currency_network_adapter, not_owner):
    currency_network_adapter.unfreeze_network(
        transaction_options={"from": not_owner}, should_fail=True
    )


def test_unfreeze_network_event(currency_network_adapter, owner, web3):
    currency_network_adapter.unfreeze_network(transaction_options={"from": owner})
    assert (
        get_single_event_of_contract(
            currency_network_adapter.contract,
            "NetworkUnfreeze",
            web3.eth.blockNumber,
        )
        is not None
    )
