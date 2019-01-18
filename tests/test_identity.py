#! pytest

import pytest
import eth_tester.exceptions
from tldeploy.core import deploy_identity


@pytest.fixture()
def test_identity_contract(web3):
    return deploy_identity(web3, "TestIdentity")


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


def test_signature_from_owner(test_identity_contract_owned_by_0, key_0, accounts):

    data = (1234).to_bytes(10, byteorder='big')
    signature = key_0.sign_msg(data).to_bytes()

    assert test_identity_contract_owned_by_0.functions.testIsSignatureFromOwner(data, signature).call() is True


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
