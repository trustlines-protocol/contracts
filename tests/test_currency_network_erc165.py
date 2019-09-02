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
    "account_management_enabled": True,
    "expiration_time": EXPIRATION_TIME,
}


@pytest.fixture
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


def test_supports_interface(currency_network_contract, web3):

    # Calculate interface id from function signatures
    ERC165_INTERFACE_ID = web3.sha3(text="supportsInterface(bytes4)")[:4].hex()

    assert (
        currency_network_contract.functions.supportsInterface(
            ERC165_INTERFACE_ID
        ).call()
        is True
    )

    # Calculate interface id from function signatures
    CURRENCY_NETWORK_INTERFACE_ID = hex(
        int.from_bytes(web3.sha3(text="name()")[:4], "big")
        ^ int.from_bytes(web3.sha3(text="symbol()")[:4], "big")
        ^ int.from_bytes(web3.sha3(text="decimals()")[:4], "big")
        ^ int.from_bytes(
            web3.sha3(text="transfer(address,uint64,uint64,address[],bytes)")[:4], "big"
        )
        ^ int.from_bytes(
            web3.sha3(
                text="transferFrom(address,address,uint64,uint64,address[],bytes)"
            )[:4],
            "big",
        )
        ^ int.from_bytes(web3.sha3(text="balance(address,address)")[:4], "big")
        ^ int.from_bytes(web3.sha3(text="creditline(address,address)")[:4], "big")
    )

    assert (
        currency_network_contract.functions.supportsInterface(
            CURRENCY_NETWORK_INTERFACE_ID
        ).call()
        is True
    )
