#! pytest
import pytest
from eth_tester.exceptions import TransactionFailed
from hexbytes import HexBytes
from tldeploy.core import deploy_network
from tldeploy.identity import MetaTransaction, Identity, Delegator
from tldeploy.signing import solidity_keccak, sign_msg_hash


@pytest.fixture(scope='session')
def delegator_address(accounts):
    return accounts[1]


@pytest.fixture(scope='session')
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope='session')
def owner_key(account_keys):
    return account_keys[0]


@pytest.fixture(scope='session')
def identity_contract(deploy_contract, web3, owner):
    identity_contract = deploy_contract("Identity")
    identity_contract.functions.init(owner).transact({'from': owner})
    web3.eth.sendTransaction({'to': identity_contract.address, 'from': owner, 'value': 1000000})
    return identity_contract


@pytest.fixture(scope='session')
def test_identity_contract(deploy_contract, web3, owner):
    test_identity_contract = deploy_contract("TestIdentity")
    test_identity_contract.functions.init(owner).transact({'from': owner})
    web3.eth.sendTransaction({'to': test_identity_contract.address, 'from': owner, 'value': 1000000})
    return test_identity_contract


@pytest.fixture(scope='session')
def identity(identity_contract, owner_key):
    return Identity(contract=identity_contract, owner_private_key=owner_key)


@pytest.fixture(scope='session')
def delegator(identity_contract, delegator_address, web3):
    return Delegator(delegator_address, web3=web3, identity_contract_abi=identity_contract.abi)


@pytest.fixture(scope='session')
def test_contract(deploy_contract):
    return deploy_contract("TestContract")


NETWORK_SETTING = {
    'name': "TestCoin",
    'symbol': "T",
    'decimals': 6,
    'fee_divisor': 0,
    'default_interest_rate': 0,
    'custom_interests': False
}


@pytest.fixture(scope='session')
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


def test_init_already_init(test_identity_contract, accounts):
    with pytest.raises(TransactionFailed):
        test_identity_contract.functions.init(accounts[0]).transact({'from': accounts[0]})


def test_signature_from_owner(test_identity_contract, owner_key):

    data_to_sign = (1234).to_bytes(10, byteorder='big')
    hash = solidity_keccak(['bytes'], [data_to_sign])
    signature = sign_msg_hash(hash, owner_key)

    assert test_identity_contract.functions.testIsSignatureValid(hash, signature).call()


def test_signature_not_owner(test_identity_contract, account_keys):
    key = account_keys[1]

    data = (1234).to_bytes(10, byteorder='big')
    hash = solidity_keccak(['bytes'], [data])
    signature = sign_msg_hash(hash, key)

    assert not test_identity_contract.functions.testIsSignatureValid(hash, signature).call()


def test_wrong_signature_from_owner(test_identity_contract, owner_key, accounts):

    data = (1234).to_bytes(10, byteorder='big')
    wrong_data = (12345678).to_bytes(10, byteorder='big')

    signature = owner_key.sign_msg(data).to_bytes()

    assert not test_identity_contract.functions.testIsSignatureValid(wrong_data, signature).call()


def test_delegated_transaction_hash(test_identity_contract, test_contract, accounts):
    to = accounts[3]
    from_ = accounts[1]
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, from_=from_, to=to, nonce=0)

    hash_by_contract = test_identity_contract.functions.testTransactionHash(
        meta_transaction.from_,
        meta_transaction.to,
        meta_transaction.value,
        meta_transaction.data,
        meta_transaction.nonce,
        meta_transaction.extra_data
    ).call()

    hash = meta_transaction.hash

    assert hash == HexBytes(hash_by_contract)


def test_delegated_transaction_function_call(identity, delegator, test_contract):
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    identity.fill_and_sign_meta_transaction(meta_transaction)
    delegator.send_signed_meta_transaction(meta_transaction)

    event = test_contract.events.TestEvent.createFilter(fromBlock=0).get_all_entries()[0]["args"]

    assert event['from'] == identity.address
    assert event['value'] == 0
    assert event['argument'] == argument


def test_delegated_transaction_transfer(web3, identity, delegator, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(to=to, value=value)

    balance_before = web3.eth.getBalance(to)
    identity.fill_and_sign_meta_transaction(meta_transaction)
    delegator.send_signed_meta_transaction(meta_transaction)

    balance_after = web3.eth.getBalance(to)

    assert balance_after - balance_before == value


def test_delegated_transaction_same_tx_fails(identity, delegator, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(to=to, value=value)
    identity.fill_and_sign_meta_transaction(meta_transaction)
    delegator.send_signed_meta_transaction(meta_transaction)

    with pytest.raises(TransactionFailed):
        delegator.send_signed_meta_transaction(meta_transaction)


def test_delegated_transaction_wrong_from(identity_contract, delegator_address, accounts, owner_key):
    from_ = accounts[3]
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(from_=from_, to=to, value=value, nonce=0)
    meta_transaction.sign(owner_key)

    with pytest.raises(TransactionFailed):
        identity_contract.functions.executeTransaction(
            meta_transaction.from_,
            meta_transaction.to,
            meta_transaction.value,
            meta_transaction.data,
            meta_transaction.nonce,
            meta_transaction.extra_data,
            meta_transaction.signature,
        ).transact({'from': delegator_address})


def test_delegated_transaction_wrong_signature(identity, delegator, accounts, account_keys):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=identity.address,
        to=to,
        value=value,
        nonce=0,
    )
    meta_transaction.sign(account_keys[3])

    with pytest.raises(TransactionFailed):
        delegator.send_signed_meta_transaction(meta_transaction)


def test_delegated_transaction_success_event(identity, delegator, test_contract):
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    identity.fill_and_sign_meta_transaction(meta_transaction)
    delegator.send_signed_meta_transaction(meta_transaction)

    event = (identity.contract.events.TransactionExecution
             .createFilter(fromBlock=0).get_all_entries()[0]["args"])

    assert event['hash'] == meta_transaction.hash
    assert event['status'] is True


def test_delegated_transaction_fail_event(identity, delegator, test_contract):
    to = test_contract.address
    function_call = test_contract.functions.fails()

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    identity.fill_and_sign_meta_transaction(meta_transaction)
    delegator.send_signed_meta_transaction(meta_transaction)

    event = (identity.contract.events.TransactionExecution
             .createFilter(fromBlock=0).get_all_entries()[0]["args"])

    assert event['hash'] == meta_transaction.hash
    assert event['status'] is False


def test_delegated_transaction_trustlines_flow(currency_network_contract, identity, delegator, accounts):
    A = identity.address
    B = accounts[3]
    to = currency_network_contract.address

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    identity.fill_and_sign_meta_transaction(meta_transaction)
    delegator.send_signed_meta_transaction(meta_transaction)

    currency_network_contract.functions.updateCreditlimits(A, 100, 100).transact({'from': B})

    function_call = currency_network_contract.functions.transfer(B, 100, 0, [B])
    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    identity.fill_and_sign_meta_transaction(meta_transaction)
    delegator.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.balance(A, B).call() == -100
