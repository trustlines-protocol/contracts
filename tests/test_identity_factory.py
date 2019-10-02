import pytest

from web3 import Web3
from hexbytes import HexBytes

from tldeploy.identity import (
    MetaTransaction,
    Identity,
    Delegate,
    get_pinned_proxy_interface,
)
from eth_tester.exceptions import TransactionFailed

from .conftest import EXTRA_DATA, EXPIRATION_TIME
from tldeploy.core import deploy_network
from tldeploy.identity import deploy_proxied_identity, build_create2_address

from deploy_tools.compile import build_initcode
from deploy_tools.deploy import deploy_compiled_contract


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    NETWORK_SETTING = {
        "name": "TestCoin",
        "symbol": "T",
        "decimals": 6,
        "fee_divisor": 0,
        "default_interest_rate": 0,
        "custom_interests": False,
        "expiration_time": EXPIRATION_TIME,
    }
    return deploy_network(web3, **NETWORK_SETTING)


@pytest.fixture(scope="session")
def proxy_factory(deploy_contract, contract_assets, web3):
    """Returns a proxy factory deployed at a deterministic address"""
    # We need to create a new account that never sent a transaction
    # to make sure the create1 address of the factory does not depend on other tests or fixtures
    aribtrary_key = f"0x{'12345678'*8}"
    new_account = web3.eth.account.from_key(aribtrary_key)
    assert web3.eth.getTransactionCount(new_account.address) == 0
    web3.eth.sendTransaction({"to": new_account.address, "value": 1 * 10 ** 18})

    proxy_factory = deploy_compiled_contract(
        abi=contract_assets["IdentityProxyFactory"]["abi"],
        bytecode=contract_assets["IdentityProxyFactory"]["bytecode"],
        web3=web3,
        private_key=new_account.key,
    )

    return proxy_factory


@pytest.fixture(scope="session")
def identity_implementation(deploy_contract, web3):

    identity_implementation = deploy_contract("Identity")
    return identity_implementation


@pytest.fixture(scope="session")
def identity_implementation_different_address(
    identity_implementation, deploy_contract, web3
):

    identity_implementation_different_address = deploy_contract("Identity")
    assert (
        identity_implementation_different_address.address
        != identity_implementation.address
    )
    return identity_implementation_different_address


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def owner_key(account_keys):
    return account_keys[0]


@pytest.fixture(scope="session")
def signature_of_owner_on_implementation(
    owner_key, identity_implementation, proxy_factory
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    to_hash = ["0x19", "0x00", proxy_factory.address, identity_implementation.address]
    to_sign = Web3.solidityKeccak(abi_types, to_hash)
    return owner_key.sign_msg_hash(to_sign).to_bytes()


@pytest.fixture(scope="session")
def signature_of_not_owner_on_implementation(
    account_keys, identity_implementation, proxy_factory
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    to_hash = ["0x19", "0x00", proxy_factory.address, identity_implementation.address]
    to_sign = Web3.solidityKeccak(abi_types, to_hash)
    return account_keys[2].sign_msg_hash(to_sign).to_bytes()


@pytest.fixture(scope="session")
def get_proxy_initcode(contract_assets):
    def initcode(args):
        interface = get_pinned_proxy_interface()
        return build_initcode(
            contract_abi=interface["abi"],
            contract_bytecode=interface["bytecode"],
            constructor_args=args,
        )

    return initcode


@pytest.fixture()
def proxied_identity_contract_with_owner(
    proxy_factory,
    identity_implementation,
    get_proxy_initcode,
    owner,
    signature_of_owner_on_implementation,
    web3,
    contract_assets,
):
    constructor_args = [owner]
    identity_proxy_initcode = get_proxy_initcode(constructor_args)

    proxy_address = build_create2_address(
        proxy_factory.address, identity_proxy_initcode
    )

    proxy_factory.functions.deployProxy(
        identity_proxy_initcode,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    ).transact()

    proxied_identity_contract = web3.eth.contract(
        address=proxy_address,
        abi=contract_assets["Identity"]["abi"],
        bytecode=contract_assets["Identity"]["bytecode"],
    )

    return proxied_identity_contract


@pytest.fixture()
def proxy_contract_with_owner(
    proxied_identity_contract_with_owner, web3, contract_assets
):

    contract = web3.eth.contract(
        address=proxied_identity_contract_with_owner.address,
        abi=contract_assets["Proxy"]["abi"],
        bytecode=contract_assets["Proxy"]["bytecode"],
    )

    return contract


@pytest.fixture()
def proxied_identity(proxied_identity_contract_with_owner, owner_key):
    return Identity(
        contract=proxied_identity_contract_with_owner, owner_private_key=owner_key
    )


@pytest.fixture(scope="session")
def delegate_address(accounts):
    return accounts[1]


@pytest.fixture(scope="session")
def delegate(contract_assets, delegate_address, web3):
    return Delegate(
        delegate_address,
        web3=web3,
        identity_contract_abi=contract_assets["Identity"]["abi"],
    )


def test_build_create2_address_conform_to_EIP1014():
    """
    Tests out two examples given in https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1014.md
    """
    assert build_create2_address(
        "0x0000000000000000000000000000000000000000", "0x00"
    ) == HexBytes("0x4D1A2e2bB4F88F0250f26Ffff098B0b30B26BF38")
    assert build_create2_address(
        Web3.toChecksumAddress("0x00000000000000000000000000000000deadbeef"),
        "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "0x00000000000000000000000000000000000000000000000000000000cafebabe",
    ) == HexBytes("0x1d8bfDC5D46DC4f61D6b6115972536eBE6A8854C")


def test_deploy_identity_proxy_at_precomputed_address(
    proxy_factory,
    identity_implementation,
    get_proxy_initcode,
    owner,
    signature_of_owner_on_implementation,
):
    """Test that we can deploy the proxy at a pre-computed address"""
    identity_proxy_initcode = get_proxy_initcode([owner])

    pre_computed_address = build_create2_address(
        proxy_factory.address, identity_proxy_initcode
    )

    proxy_factory.functions.deployProxy(
        identity_proxy_initcode,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    ).transact()

    deployement_event = proxy_factory.events.ProxyDeployment.getLogs()[0]
    identity_proxy_address = deployement_event["args"]["proxyAddress"]

    assert HexBytes(identity_proxy_address) == pre_computed_address


def test_proxy_deployment_arguments(
    proxy_factory,
    web3,
    contract_assets,
    identity_implementation,
    get_proxy_initcode,
    owner,
    signature_of_owner_on_implementation,
):
    """Test that the proxy has proper value for implementation and owner address"""
    identity_proxy_initcode = get_proxy_initcode([owner])

    proxy_factory.functions.deployProxy(
        identity_proxy_initcode,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    ).transact()

    deployement_event = proxy_factory.events.ProxyDeployment.getLogs()[0]
    identity_proxy_address = deployement_event["args"]["proxyAddress"]

    identity_proxy_contract = web3.eth.contract(
        address=identity_proxy_address,
        abi=contract_assets["Proxy"]["abi"],
        bytecode=contract_assets["Proxy"]["bytecode"],
    )
    proxied_identity_contract = web3.eth.contract(
        address=identity_proxy_address,
        abi=contract_assets["Identity"]["abi"],
        bytecode=contract_assets["Identity"]["bytecode"],
    )

    identity_implementation_address = (
        identity_proxy_contract.functions.implementation().call()
    )

    assert identity_implementation_address == identity_implementation.address
    assert proxied_identity_contract.functions.owner().call() == owner


def test_deploy_proxy_wrong_signature(
    proxy_factory,
    identity_implementation,
    get_proxy_initcode,
    owner,
    signature_of_not_owner_on_implementation,
):
    """Tests that attempting to deploy a proxy with a wrong signature will fail"""
    constructor_args = [owner]
    identity_proxy_initcode = get_proxy_initcode(constructor_args)

    with pytest.raises(TransactionFailed):
        proxy_factory.functions.deployProxy(
            identity_proxy_initcode,
            identity_implementation.address,
            signature_of_not_owner_on_implementation,
        ).transact()


def test_change_identity_implementation(
    proxy_contract_with_owner,
    identity_implementation,
    identity_implementation_different_address,
    proxied_identity,
    delegate,
):

    assert (
        proxy_contract_with_owner.functions.implementation().call()
        == identity_implementation.address
    )

    to = proxy_contract_with_owner.address
    function_call = proxy_contract_with_owner.functions.setImplementation(
        identity_implementation_different_address.address
    )

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = proxied_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert (
        proxy_contract_with_owner.functions.implementation().call()
        == identity_implementation_different_address.address
    )


def test_clientlib_calculate_proxy_address(proxy_factory, get_proxy_initcode, owner):
    """Give out some tests values for pre calculating the proxy address in the clientlib tests"""
    identity_proxy_initcode = get_proxy_initcode([owner])

    assert owner == "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
    assert proxy_factory.address == "0x8688966AE53807c273D8B9fCcf667F0A0a91b1d3"

    pre_computed_address = build_create2_address(
        proxy_factory.address, identity_proxy_initcode
    )
    assert pre_computed_address.hex() == "0xfc22014081799f6eb79fecca92486ebdd276229b"


def test_delegated_transaction_trustlines_flow_via_proxy(
    currency_network_contract, proxied_identity, delegate, accounts
):
    A = proxied_identity.address
    B = accounts[3]
    to = currency_network_contract.address

    function_call = currency_network_contract.functions.updateCreditlimits(B, 100, 100)
    meta_transaction = proxied_identity.filled_and_signed_meta_transaction(
        MetaTransaction.from_function_call(function_call, to=to)
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    currency_network_contract.functions.updateCreditlimits(A, 100, 100).transact(
        {"from": B}
    )

    function_call = currency_network_contract.functions.transfer(
        B, 100, 0, [B], EXTRA_DATA
    )
    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = proxied_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert currency_network_contract.functions.balance(A, B).call() == -100


def test_deploy_identity_proxy(
    web3,
    proxy_factory,
    identity_implementation,
    signature_of_owner_on_implementation,
    owner,
    get_proxy_initcode,
):
    proxy = deploy_proxied_identity(
        web3,
        proxy_factory.address,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    )

    identity_proxy_initcode = get_proxy_initcode([owner])
    pre_computed_address = build_create2_address(
        proxy_factory.address, identity_proxy_initcode
    )

    assert proxy.address == pre_computed_address
    assert proxy.functions.implementation().call() == identity_implementation.address
