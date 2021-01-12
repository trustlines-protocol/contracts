#! pytest
import pytest

from tests.currency_network.conftest import deploy_test_network, NETWORK_SETTING


@pytest.fixture
def currency_network_contract(web3):
    return deploy_test_network(web3, NETWORK_SETTING)


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
    CURRENCY_NETWORK_INTERFACE_ID = (
        int.from_bytes(web3.sha3(text="name()")[:4], "big")
        ^ int.from_bytes(web3.sha3(text="symbol()")[:4], "big")
        ^ int.from_bytes(web3.sha3(text="decimals()")[:4], "big")
        ^ int.from_bytes(
            web3.sha3(text="transfer(uint64,uint64,address[],bytes)")[:4], "big"
        )
        ^ int.from_bytes(
            web3.sha3(text="transferFrom(uint64,uint64,address[],bytes)")[:4], "big"
        )
        ^ int.from_bytes(web3.sha3(text="balance(address,address)")[:4], "big")
        ^ int.from_bytes(web3.sha3(text="creditline(address,address)")[:4], "big")
    ).to_bytes(4, byteorder="big")

    assert (
        currency_network_contract.functions.supportsInterface(
            CURRENCY_NETWORK_INTERFACE_ID
        ).call()
        is True
    )
