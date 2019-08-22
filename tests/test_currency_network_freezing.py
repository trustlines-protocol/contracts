import pytest

from tldeploy.core import deploy_network
import eth_tester.exceptions

from .conftest import EXPIRATION_TIME


NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 0,
    "default_interest_rate": 0,
    "custom_interests": False,
    "currency_network_contract_name": "TestCurrencyNetwork",
    "expiration_time": EXPIRATION_TIME,
}


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


def test_freeze_too_soon(currency_network_contract):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.freezeNetwork().transact()


def test_freeze(currency_network_contract, chain):
    assert currency_network_contract.functions.isFrozen().call() is False

    chain.time_travel(EXPIRATION_TIME)
    chain.mine_block()

    currency_network_contract.functions.freezeNetwork().transact()

    assert currency_network_contract.functions.isFrozen().call() is True
