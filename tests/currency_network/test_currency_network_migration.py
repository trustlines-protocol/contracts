#! pytest

import pytest

from tldeploy.core import deploy_network
import eth_tester.exceptions

from tests.conftest import EXPIRATION_TIME

ADDRESS_0 = "0x0000000000000000000000000000000000000000"

NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 0,
    "default_interest_rate": 0,
    "custom_interests": False,
    "currency_network_contract_name": "CurrencyNetworkOwnable",
    "expiration_time": EXPIRATION_TIME,
}


def get_events_of_contract(contract, event_name, from_block=0):
    return list(getattr(contract.events, event_name).getLogs(fromBlock=from_block))


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def not_owner(accounts, owner):
    not_owner = accounts[1]
    assert not_owner != owner
    return not_owner


@pytest.fixture(scope="session")
def currency_network_contract(web3, owner):
    settings = NETWORK_SETTING.copy()
    settings["transaction_options"] = {"from": owner}
    return deploy_network(web3, **NETWORK_SETTING)


def test_remove_owner(currency_network_contract, owner):
    currency_network_contract.functions.removeOwner().transact({"from": owner})
    assert currency_network_contract.functions.owner().call() == ADDRESS_0


def test_remover_owner_not_owner(currency_network_contract, not_owner):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.removeOwner().transact({"from": not_owner})


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


def test_set_debt_not_owner(currency_network_contract, not_owner, accounts):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.setDebt(
            accounts[1], accounts[2], 123
        ).transact({"from": not_owner})


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
