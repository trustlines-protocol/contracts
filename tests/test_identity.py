#! pytest

import pytest
import eth_tester.exceptions
from tldeploy.core import deploy
from web3 import Web3

def data_delegate_transaction(to, from_, value, data, nonce, extrahash):
    pass


@pytest.fixture()
def identity_contract(web3):
    return deploy("Identity", web3)


@pytest.fixture()
def test_identity_contract(web3):
    return deploy("TestIdentity", web3)


@pytest.fixture()
def mock_contract(web3):
    return deploy("Mock", web3)


@pytest.fixture()
def mock_contract_address(mock_contract, web3):
    return mock_contract.address


@pytest.fixture()
def identity_contract_owned_by_0(identity_contract, web3, accounts):

    owner = accounts[0]
    identity_contract.functions.init(owner).transact({'from': accounts[0]})
    return identity_contract


@pytest.fixture()
def test_identity_contract_owned_by_0(test_identity_contract, web3, accounts):

    owner = accounts[0]
    test_identity_contract.functions.init(owner).transact({'from': accounts[0]})
    return test_identity_contract


@pytest.fixture()
def key_0(ethereum_tester, accounts):
    return ethereum_tester.backend.account_keys[0]


def test_init_already_init(test_identity_contract_owned_by_0, accounts):

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        test_identity_contract_owned_by_0.functions.init(accounts[0]).transact({'from': accounts[0]})


def test_signature_from_owner(test_identity_contract_owned_by_0, key_0):

    data_to_sign = (1234).to_bytes(10, byteorder='big')
    signature = key_0.sign_msg(data_to_sign).to_bytes()
    hash = Web3.soliditySha3(['bytes'], [data_to_sign])

    assert test_identity_contract_owned_by_0.functions.testIsSignatureFromOwner(hash, signature).call() is True


def test_signature_not_owner(test_identity_contract_owned_by_0, key_0, ethereum_tester, accounts):

    data = (1234).to_bytes(10, byteorder='big')
    private_key = ethereum_tester.backend.account_keys[1]
    signature = private_key.sign_msg(data).to_bytes()

    assert test_identity_contract_owned_by_0.functions.testIsSignatureFromOwner(data, signature).call() is False


def test_wrong_signature_from_owner(test_identity_contract_owned_by_0, key_0, accounts):

    data = (1234).to_bytes(10, byteorder='big')
    wrong_data = (12345678).to_bytes(10, byteorder='big')

    signature = key_0.sign_msg(data).to_bytes()

    assert test_identity_contract_owned_by_0.functions.testIsSignatureFromOwner(wrong_data, signature).call() is False


def test_execute_delegated_transaction(identity_contract_owned_by_0, key_0, mock_contract, accounts, web3):

    latest_block_number = web3.eth.blockNumber
    delegate = accounts[1]

    to = mock_contract.address
    from_ = identity_contract_owned_by_0.address
    value = 1000

    data_for_mock_contract = (1234).to_bytes(10, byteorder='big')
    data_for_identity_contract = mock_contract.functions.testFunction(data_for_mock_contract).buildTransaction()['data']

    nonce = 0
    extra_hash = (0).to_bytes(10, byteorder='big')

    hash = Web3.soliditySha3(['address', 'address', 'uint256', 'bytes', 'uint256', 'bytes'], [from_, to, value, data_for_identity_contract, nonce, extra_hash])
    signature = web3.eth.account.signHash(hash, key_0)

    # signature = key_0.sign_msg(to, from_).to_bytes()  # We should not hash before signing (sign data not hash)

    identity_contract_owned_by_0.functions.executeDelegatedTransaction(from_, to, value, data_for_identity_contract, nonce, extra_hash, signature).transact({'from': accounts[0], 'value': value})

    event = mock_contract.events.TestFunctionCalled.createFilter(
        fromBlock=latest_block_number
        ).get_all_entries()[0]["args"]

    assert event['from'] == identity_contract_owned_by_0.address
    assert event['value'] == value
    assert event['data'] == data_for_mock_contract
