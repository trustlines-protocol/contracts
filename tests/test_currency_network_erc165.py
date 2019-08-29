#! pytest
import pytest

from tldeploy.core import deploy_network
from .conftest import EXPIRATION_TIME


NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 0,
    "default_interest_rate": 0,
    "custom_interests": False,
    "currency_network_contract_name": "TestCurrencyNetwork",
    "set_account_enabled": True,
    "expiration_time": EXPIRATION_TIME,
}

ERC165_INTERFACE_ID = "0x01ffc9a7"
CURRENCY_NETWORK_INTERFACE_ID = "0xdcd45f8a"


@pytest.fixture
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


def test_supports_interface(currency_network_contract):
    assert (
        currency_network_contract.functions.supportsInterface(
            ERC165_INTERFACE_ID
        ).call()
        == True
    )
    assert (
        currency_network_contract.functions.supportsInterface(
            CURRENCY_NETWORK_INTERFACE_ID
        ).call()
        == True
    )
