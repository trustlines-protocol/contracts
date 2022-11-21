#! pytest
import pytest
import attr
from eth_tester.exceptions import TransactionFailed
from hexbytes import HexBytes
from tldeploy.core import deploy_network, deploy_identity, NetworkSettings
from tldeploy.identity import (
    MetaTransaction,
    UnexpectedIdentityContractException,
    build_create2_address,
    MetaTransactionStatus,
)
from tldeploy.signing import solidity_keccak, sign_msg_hash

from tests.conftest import EXTRA_DATA
from deploy_tools.compile import build_initcode


def get_transaction_status(web3, tx_id):
    return bool(web3.eth.getTransactionReceipt(tx_id).get("status"))


@pytest.fixture(params=range(2))
def each_identity_contract(request, identity_contract, proxied_identity_contract):
    """Allows to test against raw identity contract and the proxied identity contract"""
    return [identity_contract, proxied_identity_contract][request.param]


@pytest.fixture(params=range(2))
def each_identity(request, identity, proxied_identity):
    """Allows to test against raw identity and the proxied identity"""
    return [identity, proxied_identity][request.param]


@pytest.fixture(scope="session")
def test_contract(deploy_contract):
    return deploy_contract("TestContract")


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, NetworkSettings())


@pytest.fixture(scope="session")
def second_currency_network_contract(web3):
    return deploy_network(web3, NetworkSettings())


@pytest.fixture(scope="session")
def test_contract_initcode(contract_assets):

    interface = contract_assets["TestContract"]
    return build_initcode(
        contract_abi=interface["abi"], contract_bytecode=interface["bytecode"]
    )


@pytest.fixture(scope="session")
def test_contract_abi(contract_assets):
    return contract_assets["TestContract"]["abi"]


@pytest.fixture(scope="session")
def non_payable_contract_inticode(contract_assets):
    interface = contract_assets["Identity"]
    return build_initcode(
        contract_abi=interface["abi"], contract_bytecode=interface["bytecode"]
    )


def test_init_already_init(each_identity_contract, accounts):
    with pytest.raises(TransactionFailed):
        each_identity_contract.functions.init(accounts[0], 0).transact(
            {"from": accounts[0]}
        )


def test_signature_from_owner(each_identity_contract, owner_key):

    data_to_sign = (1234).to_bytes(10, byteorder="big")
    hash = solidity_keccak(["bytes"], [data_to_sign])
    signature = sign_msg_hash(hash, owner_key)

    assert each_identity_contract.functions.validateSignature(hash, signature).call()


def test_signature_not_owner(each_identity_contract, account_keys):
    key = account_keys[1]

    data = (1234).to_bytes(10, byteorder="big")
    hash = solidity_keccak(["bytes"], [data])
    signature = sign_msg_hash(hash, key)

    assert not each_identity_contract.functions.validateSignature(
        hash, signature
    ).call()


def test_wrong_signature_from_owner(each_identity_contract, owner_key):

    data = (1234).to_bytes(10, byteorder="big")
    wrong_data = (12345678).to_bytes(10, byteorder="big")

    signature = owner_key.sign_msg(data).to_bytes()

    assert not each_identity_contract.functions.validateSignature(
        wrong_data, signature
    ).call()


def test_meta_transaction_signature_corresponds_to_clientlib_signature(
    each_identity, owner_key
):
    # Tests that the signature obtained from the contracts and the clientlib implementation match,
    # If this test needs to be changed, the corresponding test in the clientlib should also be changed
    # See: clientlib/tests/unit/IdentityWallet.test.ts: 'should sign meta-transaction'
    from_ = "0xF2E246BB76DF876Cef8b38ae84130F4F55De395b"
    to = "0x51a240271AB8AB9f9a21C82d9a85396b704E164d"
    chain_id = 0
    value = 0
    data = "0x46432830000000000000000000000000000000000000000000000000000000000000000a"
    base_fee = 1
    gas_price = 123
    gas_limit = 456
    fee_recipient = "0xF2E246BB76DF876Cef8b38ae84130F4F55De395b"
    currency_network_of_fees = "0x51a240271AB8AB9f9a21C82d9a85396b704E164d"
    nonce = 1
    time_limit = 123456

    meta_transaction = MetaTransaction(
        from_=from_,
        chain_id=chain_id,
        to=to,
        value=value,
        data=data,
        base_fee=base_fee,
        gas_price=gas_price,
        gas_limit=gas_limit,
        fee_recipient=fee_recipient,
        currency_network_of_fees=currency_network_of_fees,
        nonce=nonce,
        time_limit=time_limit,
    )

    signature = each_identity.signed_meta_transaction(meta_transaction).signature

    assert (
        str(owner_key)
        == "0x0000000000000000000000000000000000000000000000000000000000000001"
    )
    assert (
        signature.hex()
        == "639db755a4e0642c2ec76485cf623c58b635c54f9ce375088fad40a128779d7a060"
        "ceb63129eb9681216a844a0577184b1d3266fc6ac00fbbe23e72b592c33c200"
    )


def test_delegated_transaction_hash(each_identity_contract, test_contract, accounts):
    to = accounts[3]
    from_ = each_identity_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(
        function_call, from_=from_, to=to, nonce=0
    )

    hash_by_contract = each_identity_contract.functions.transactionHash(
        meta_transaction.to,
        meta_transaction.value,
        meta_transaction.data,
        meta_transaction.base_fee,
        meta_transaction.gas_price,
        meta_transaction.gas_limit,
        meta_transaction.fee_recipient,
        meta_transaction.currency_network_of_fees,
        meta_transaction.nonce,
        meta_transaction.time_limit,
        meta_transaction.operation_type.value,
    ).call()

    hash = meta_transaction.hash

    assert hash == HexBytes(hash_by_contract)


def test_delegated_transaction_function_call(
    each_identity, delegate, test_contract, web3
):
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    event = test_contract.events.TestEvent.createFilter(fromBlock=0).get_all_entries()[
        0
    ]["args"]

    assert get_transaction_status(web3, tx_id)
    assert event["from"] == each_identity.address
    assert event["value"] == 0
    assert event["argument"] == argument


def test_delegated_transaction_transfer(web3, each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(to=to, value=value)

    balance_before = web3.eth.getBalance(to)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    balance_after = web3.eth.getBalance(to)

    assert get_transaction_status(web3, tx_id)
    assert balance_after - balance_before == value


def test_delegated_transaction_same_tx_fails(each_identity, delegate, accounts, web3):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(to=to, value=value)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction)


def test_delegated_transaction_wrong_from(
    each_identity_contract, delegate_address, accounts, owner_key, chain_id
):
    from_ = accounts[3]
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=from_, to=to, value=value, nonce=0, chain_id=chain_id
    ).signed(owner_key)

    with pytest.raises(TransactionFailed):
        each_identity_contract.functions.executeTransaction(
            meta_transaction.to,
            meta_transaction.value,
            meta_transaction.data,
            meta_transaction.base_fee,
            meta_transaction.gas_price,
            meta_transaction.gas_limit,
            meta_transaction.fee_recipient,
            meta_transaction.currency_network_of_fees,
            meta_transaction.nonce,
            meta_transaction.time_limit,
            meta_transaction.operation_type.value,
            meta_transaction.signature,
        ).transact({"from": delegate_address})


def test_delegated_transaction_wrong_signature(
    each_identity, delegate, accounts, account_keys, web3, chain_id
):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=each_identity.address, to=to, value=value, nonce=0, chain_id=chain_id
    ).signed(account_keys[3])

    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction)


def test_delegated_transaction_success_event(each_identity, delegate, test_contract):
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    event = each_identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    assert event["hash"] == meta_transaction.hash
    assert event["status"] is True


def test_delegated_transaction_fail_event(each_identity, delegate, test_contract):
    to = test_contract.address
    function_call = test_contract.functions.fails()

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    event = each_identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    assert event["hash"] == meta_transaction.hash
    assert event["status"] is False


def test_delegated_transaction_trustlines_flow(
    currency_network_contract, each_identity, delegate, accounts
):
    A = each_identity.address
    B = accounts[3]
    to = currency_network_contract.address

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    currency_network_contract.functions.updateCreditlimits(A, 100, 100).transact(
        {"from": B}
    )

    function_call = currency_network_contract.functions.transfer(
        100, 0, [A, B], EXTRA_DATA
    )
    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.balance(A, B).call() == -100


def test_delegated_transaction_nonce_zero(each_identity, delegate, web3, accounts):
    to = accounts[2]
    value1 = 1000
    value2 = 1001

    balance_before = web3.eth.getBalance(to)

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value1, nonce=0)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value2, nonce=0)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)
    delegate.send_signed_meta_transaction(meta_transaction2)

    balance_after = web3.eth.getBalance(to)

    assert balance_after - balance_before == value1 + value2


def test_delegated_transaction_nonce_increase(each_identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000

    balance_before = web3.eth.getBalance(to)

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=2)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)
    delegate.send_signed_meta_transaction(meta_transaction2)

    balance_after = web3.eth.getBalance(to)

    assert balance_after - balance_before == value + value


def test_delegated_transaction_same_nonce_fails(
    each_identity, delegate, web3, accounts
):
    to = accounts[2]
    value = 1000

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction2)


def test_delegated_transaction_nonce_gap_fails(each_identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=3)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction2)


def test_meta_transaction_time_limit_valid(each_identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000
    time_limit = web3.eth.getBlock("latest").timestamp + 1000

    meta_transaction = MetaTransaction(to=to, value=value, time_limit=time_limit)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    assert get_transaction_status(web3, tx_id)


def test_meta_transaction_no_limit_valid(each_identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000
    time_limit = 0

    meta_transaction = MetaTransaction(to=to, value=value, time_limit=time_limit)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    assert get_transaction_status(web3, tx_id)


def test_meta_transaction_time_limit_invalid(each_identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000
    time_limit = web3.eth.getBlock("latest").timestamp - 1

    meta_transaction = MetaTransaction(to=to, value=value, time_limit=time_limit)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )

    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction)


def test_validate_same_tx(each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert not delegate.validate_meta_transaction(meta_transaction)


def test_validate_from_no_code(delegate, accounts, owner_key, chain_id):
    from_ = accounts[3]
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=from_, to=to, value=value, nonce=0, chain_id=chain_id
    ).signed(owner_key)

    with pytest.raises(UnexpectedIdentityContractException):
        delegate.validate_meta_transaction(meta_transaction)


def test_validate_from_wrong_contract(
    delegate, accounts, owner_key, currency_network_contract, chain_id
):
    from_ = currency_network_contract.address
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=from_, to=to, value=value, nonce=0, chain_id=chain_id
    ).signed(owner_key)

    with pytest.raises(UnexpectedIdentityContractException):
        delegate.validate_meta_transaction(meta_transaction)


def test_validate_wrong_signature(
    each_identity, delegate, accounts, account_keys, chain_id
):
    to = accounts[2]
    value = 1000

    meta_transaction = MetaTransaction(
        from_=each_identity.address, to=to, value=value, nonce=0, chain_id=chain_id
    ).signed(account_keys[3])

    assert not delegate.validate_meta_transaction(meta_transaction)


def test_validate_same_nonce_fails(each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    assert not delegate.validate_meta_transaction(meta_transaction2)


def test_validate_nonce_gap_fails(each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=3)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    assert not delegate.validate_meta_transaction(meta_transaction2)


def test_validate_valid_transfer(each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value)
    )

    assert delegate.validate_meta_transaction(meta_transaction)


def test_validate_valid_nonce_increase(each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=2)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)

    assert delegate.validate_meta_transaction(meta_transaction2)


def test_estimate_gas(each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value)
    )

    assert isinstance(
        delegate.estimate_gas_signed_meta_transaction(meta_transaction), int
    )


def test_deploy_identity(web3, delegate, owner, owner_key, test_contract):
    each_identity_contract = deploy_identity(web3, owner)

    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(
        function_call, to=to, from_=each_identity_contract.address, nonce=0
    ).signed(owner_key)
    delegate.send_signed_meta_transaction(meta_transaction)

    assert (
        len(test_contract.events.TestEvent.createFilter(fromBlock=0).get_all_entries())
        > 0
    )


def test_next_nonce(each_identity, delegate, accounts):
    to = accounts[2]
    value = 1000

    meta_transaction1 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=1)
    )
    meta_transaction2 = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=to, value=value, nonce=2)
    )

    delegate.send_signed_meta_transaction(meta_transaction1)
    delegate.send_signed_meta_transaction(meta_transaction2)

    assert delegate.get_next_nonce(each_identity.address) == 3


def test_meta_transaction_with_fees_increases_debt(
    currency_network_contract, each_identity, delegate, delegate_address, accounts
):
    A = each_identity.address
    B = accounts[3]
    to = currency_network_contract.address
    base_fee = 123

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to, base_fee=base_fee)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert (
        currency_network_contract.functions.getDebt(A, delegate_address).call()
        == base_fee
    )


def test_failing_meta_transaction_with_fees_does_not_increases_debt(
    currency_network_contract, each_identity, delegate, delegate_address, accounts
):
    A = each_identity.address
    B = accounts[3]
    to = currency_network_contract.address
    base_fee = 123

    function_call = currency_network_contract.functions.transfer(100, 100, [A, B], b"")
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to, base_fee=base_fee)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.getDebt(A, delegate_address).call() == 0


def test_tracking_delegation_fee_in_different_network(
    currency_network_contract,
    second_currency_network_contract,
    each_identity,
    delegate,
    delegate_address,
    accounts,
):
    A = each_identity.address
    B = accounts[3]
    to = currency_network_contract.address
    base_fee = 123

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(
            function_call,
            to=to,
            base_fee=base_fee,
            currency_network_of_fees=second_currency_network_contract.address,
        )
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.getDebt(A, delegate_address).call() == 0
    assert (
        second_currency_network_contract.functions.getDebt(A, delegate_address).call()
        == base_fee
    )


def test_meta_transaction_gas_fee(
    currency_network_contract, each_identity, delegate, delegate_address, accounts
):
    A = each_identity.address
    B = accounts[3]
    to = currency_network_contract.address
    base_fee = 123
    effective_gas_price = 1000
    contract_gas_price_divisor = 10**6
    gas_price = effective_gas_price * contract_gas_price_divisor

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(
            function_call, to=to, base_fee=base_fee, gas_price=gas_price
        )
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    effective_fee = currency_network_contract.functions.getDebt(
        A, delegate_address
    ).call()

    assert (effective_fee - base_fee) % effective_gas_price == 0
    assert effective_fee - base_fee != 0


def test_meta_transaction_gas_limit(each_identity, delegate, web3, accounts):
    to = accounts[2]
    value = 1000
    gas_limit = 456

    meta_transaction = MetaTransaction(to=to, value=value, gas_limit=gas_limit)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )

    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction)


def test_meta_transaction_fee_recipient(
    currency_network_contract, each_identity, delegate, delegate_address, accounts
):
    A = each_identity.address
    B = accounts[3]
    to = currency_network_contract.address
    base_fee = 123

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = MetaTransaction.from_function_call(
        function_call, to=to, base_fee=base_fee
    )
    meta_transaction = attr.evolve(meta_transaction, fee_recipient=B)
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    debt_A_B = currency_network_contract.functions.getDebt(A, B).call()
    debt_A_delegate = currency_network_contract.functions.getDebt(
        A, delegate_address
    ).call()

    assert debt_A_B == base_fee
    assert debt_A_delegate == 0

    fee_payment_event = each_identity.contract.events.FeePayment().getLogs()[-1]
    assert fee_payment_event["args"]["value"] == base_fee
    assert fee_payment_event["args"]["recipient"] == B


def test_meta_transaction_delegate_call(
    each_identity, delegate, delegate_address, web3, test_contract
):
    to = test_contract.address
    argument = 123
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = attr.evolve(
        meta_transaction, operation_type=MetaTransaction.OperationType.DELEGATE_CALL
    )
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    execution_event = each_identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    # assert that the delegate call was successful
    assert get_transaction_status(web3, tx_id)
    assert execution_event["hash"] == meta_transaction.hash
    assert execution_event["status"] is True

    proxied_test_contract = web3.eth.contract(
        each_identity.contract.address, abi=test_contract.abi
    )
    test_event = proxied_test_contract.events.TestEvent.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    # assert that the successful operation was indeed a delegate call
    # by checking that `from` is delegate_address and not identity_address
    assert test_event["from"] == delegate_address
    assert test_event["value"] == 0
    assert test_event["argument"] == argument


def test_meta_transaction_delegate_call_fail(
    each_identity, delegate, web3, test_contract
):
    to = test_contract.address
    function_call = test_contract.functions.fails()

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = attr.evolve(
        meta_transaction, operation_type=MetaTransaction.OperationType.DELEGATE_CALL
    )
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    tx_id = delegate.send_signed_meta_transaction(meta_transaction)

    execution_event = each_identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    assert get_transaction_status(web3, tx_id)
    assert execution_event["hash"] == meta_transaction.hash
    assert execution_event["status"] is False


@pytest.mark.parametrize(
    "operation_type",
    [MetaTransaction.OperationType.CREATE, MetaTransaction.OperationType.CREATE2],
)
def test_meta_transaction_create_contract(
    each_identity,
    delegate,
    test_contract_initcode,
    test_contract_abi,
    web3,
    operation_type,
):
    deployed_contract_balance = 123
    meta_transaction = MetaTransaction(
        operation_type=operation_type,
        data=test_contract_initcode,
        value=deployed_contract_balance,
    )
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    # It seems that web3 fails to estimate gas for deployment transactions
    tx_id = delegate.send_signed_meta_transaction(
        meta_transaction, transaction_options={"gas": 1_000_000}
    )

    execution_event = each_identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    # assert that the create was successful
    assert get_transaction_status(web3, tx_id)
    assert execution_event["hash"] == meta_transaction.hash
    assert execution_event["status"] is True

    deploy_event = each_identity.contract.events.ContractDeployment.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]
    deployed_contract = web3.eth.contract(
        deploy_event["deployed"], abi=test_contract_abi
    )

    # check that the contract was indeed deployed
    assert deployed_contract.functions.testPublicValue().call() == 123456
    assert web3.eth.getBalance(deployed_contract.address) == deployed_contract_balance

    if operation_type == MetaTransaction.OperationType.CREATE2:
        # check that create2 was used and we could pre-compute the deployed address
        create_2_address = build_create2_address(
            each_identity.address, test_contract_initcode
        )
        assert deployed_contract.address == create_2_address


@pytest.mark.parametrize(
    "operation_type",
    [MetaTransaction.OperationType.CREATE, MetaTransaction.OperationType.CREATE2],
)
def test_meta_transaction_create_contract_fails(
    each_identity, delegate, non_payable_contract_inticode, web3, operation_type
):
    """Test that the status in the event is False when deployment fails"""
    # To make the deployment fail we deploy a contract whose constructor is not payable
    # and transfer it eth during deployment
    deployed_contract_balance = 123
    meta_transaction = MetaTransaction(
        operation_type=operation_type,
        data=non_payable_contract_inticode,
        value=deployed_contract_balance,
    )
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    # It seems that web3 fails to estimate gas for deployment transactions
    tx_id = delegate.send_signed_meta_transaction(
        meta_transaction, transaction_options={"gas": 1_000_000}
    )

    execution_event = each_identity.contract.events.TransactionExecution.createFilter(
        fromBlock=0
    ).get_all_entries()[0]["args"]

    # assert that the create failed
    assert get_transaction_status(web3, tx_id)
    assert execution_event["hash"] == meta_transaction.hash
    assert execution_event["status"] is False

    deploy_events = each_identity.contract.events.ContractDeployment.createFilter(
        fromBlock=0
    ).get_all_entries()
    assert len(deploy_events) == 0


def test_get_version(each_identity_contract):
    assert each_identity_contract.functions.version().call() == 1


def test_revoke_meta_transaction_hash(each_identity, delegate, test_contract):
    """Test that we can revoke a meta-tx that uses hash anti-replay mechanism via canceling the hash"""
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to, nonce=0)
    )
    revoke_function_call = each_identity.contract.functions.cancelTransaction(
        meta_transaction.hash
    )
    revoke_meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(
            revoke_function_call, to=each_identity.address
        )
    )
    delegate.send_signed_meta_transaction(revoke_meta_transaction)

    events = each_identity.contract.events.TransactionCancellation().getLogs()

    assert len(events) == 1
    assert events[0]["args"]["hash"] == meta_transaction.hash

    assert not delegate.validate_meta_transaction(meta_transaction)
    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction)


def test_cannot_revoke_executed_transaction(each_identity, delegate, test_contract):
    """Test that we can not revoke a meta-tx that was already executed"""
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to, nonce=0)
    )
    delegate.send_signed_meta_transaction(meta_transaction)
    revoke_function_call = each_identity.contract.functions.cancelTransaction(
        meta_transaction.hash
    )
    revoke_meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(
            revoke_function_call, to=each_identity.address
        )
    )
    delegate.send_signed_meta_transaction(revoke_meta_transaction)

    events = each_identity.contract.events.TransactionCancellation().getLogs()
    assert len(events) == 0


def test_revoke_meta_transaction_nonce(each_identity, delegate, test_contract):
    """Test that we can revoke a meta-tx that uses nonce anti-replay mechanism via using the nonce"""
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )

    revoke_meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=each_identity.address, nonce=meta_transaction.nonce)
    )
    delegate.send_signed_meta_transaction(revoke_meta_transaction)

    assert not delegate.validate_meta_transaction(meta_transaction)
    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction)


def test_reveoke_meta_transaction_nonce_via_hash(
    each_identity, delegate, test_contract
):
    """Test that we can revoke a meta-tx that uses nonce anti-replay mechanism via canceling the hash"""
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )

    revoke_function_call = each_identity.contract.functions.cancelTransaction(
        meta_transaction.hash
    )
    revoke_meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(
            revoke_function_call, to=each_identity.address
        )
    )
    delegate.send_signed_meta_transaction(revoke_meta_transaction)

    assert not delegate.validate_meta_transaction(meta_transaction)
    with pytest.raises(TransactionFailed):
        delegate.send_signed_meta_transaction(meta_transaction)


def test_execute(owner, accounts, each_identity_contract, web3):
    recipient = accounts[1]
    transfer_value = 123
    initial_recipient_balance = web3.eth.getBalance(recipient)
    each_identity_contract.functions.execute(
        recipient, transfer_value, b"", 0, 0
    ).transact({"from": owner})
    post_recipient_balance = web3.eth.getBalance(recipient)

    assert post_recipient_balance - initial_recipient_balance == transfer_value


def test_execute_below_time_limit(owner, accounts, each_identity_contract, web3):
    recipient = accounts[1]
    transfer_value = 123
    time_limit = web3.eth.getBlock("latest").timestamp + 100
    each_identity_contract.functions.execute(
        recipient, transfer_value, b"", time_limit, 0
    ).transact({"from": owner})


def test_execute_expired_time_limit(owner, accounts, each_identity_contract, web3):
    recipient = accounts[1]
    transfer_value = 123
    time_limit = web3.eth.getBlock("latest").timestamp - 1
    with pytest.raises(TransactionFailed):
        each_identity_contract.functions.execute(
            recipient, transfer_value, b"", time_limit, 0
        ).transact({"from": owner})


def test_send_same_function_call_twice_without_nonce_tracking(
    each_identity, test_contract, delegate
):
    """Test that we can send two similar transactions to a contract by selecting a random nonce > 2**255"""
    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    max_nonce = 2**255
    random_gap = 123456

    meta_transaction = MetaTransaction.from_function_call(
        function_call, to=to, nonce=max_nonce
    )
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    meta_transaction = MetaTransaction.from_function_call(
        function_call, to=to, nonce=max_nonce + random_gap
    )
    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    events = test_contract.events.TestEvent.createFilter(fromBlock=0).get_all_entries()

    for event in events:
        assert event["args"]["from"] == each_identity.address
        assert event["args"]["value"] == 0
        assert event["args"]["argument"] == argument


def test_get_successful_meta_transaction_status(each_identity, delegate):

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=each_identity.address)
    )

    delegate.send_signed_meta_transaction(meta_transaction)

    meta_tx_status = delegate.get_meta_transaction_status(
        each_identity.address, meta_transaction.hash
    )
    assert meta_tx_status == MetaTransactionStatus.SUCCESS


def test_get_failed_meta_transaction_status(each_identity, delegate, test_contract):

    meta_transaction = MetaTransaction.from_function_call(
        test_contract.functions.fails(), to=test_contract.address
    )

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )

    delegate.send_signed_meta_transaction(meta_transaction)

    meta_tx_status = delegate.get_meta_transaction_status(
        each_identity.address, meta_transaction.hash
    )
    assert meta_tx_status == MetaTransactionStatus.FAILURE


def test_get_not_found_meta_transaction_status(each_identity, delegate):

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=each_identity.address)
    )

    meta_tx_status = delegate.get_meta_transaction_status(
        each_identity.address, meta_transaction.hash
    )
    assert meta_tx_status == MetaTransactionStatus.NOT_FOUND


def test_set_delegate_transaction_params(web3, each_identity, delegate, accounts):

    meta_transaction = each_identity.filled_and_signed_meta_transaction(
        MetaTransaction(to=each_identity.address)
    )

    transaction_options = {"gasPrice": 10000, "gas": 1000000, "from": accounts[2]}

    assert transaction_options["from"] != delegate.delegate_address
    tx_hash = delegate.send_signed_meta_transaction(
        meta_transaction, transaction_options=transaction_options.copy()
    )

    tx = web3.eth.getTransaction(tx_hash)

    assert tx["from"] == transaction_options["from"]
    assert tx["gas"] == transaction_options["gas"]
    assert tx["gasPrice"] == transaction_options["gasPrice"]
