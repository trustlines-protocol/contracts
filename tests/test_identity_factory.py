import pytest

from web3 import Web3
from hexbytes import HexBytes

from tldeploy.identity import MetaTransaction, Identity, Delegate
from eth_tester.exceptions import TransactionFailed

from .conftest import EXTRA_DATA, EXPIRATION_TIME
from tldeploy.core import deploy_network
from tldeploy.identity import deploy_proxied_identity, build_create2_address

from deploy_tools.compile import build_initcode


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
def proxy_factory(deploy_contract, web3):

    proxy_factory = deploy_contract("IdentityProxyFactory")
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
def get_initcode(contract_assets):
    def initcode(contract_name, args):
        return build_initcode(
            contract_abi=contract_assets[contract_name]["abi"],
            contract_bytecode=contract_assets[contract_name]["bytecode"],
            constructor_args=args,
        )

    return initcode


@pytest.fixture()
def proxied_identity_contract_with_owner(
    proxy_factory,
    identity_implementation,
    get_initcode,
    owner,
    signature_of_owner_on_implementation,
    web3,
    contract_assets,
):
    constructor_args = [owner]
    identity_proxy_initcode = get_initcode("Proxy", constructor_args)

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
    get_initcode,
    owner,
    signature_of_owner_on_implementation,
):
    """Test that we can deploy the proxy at a pre-computed address"""
    identity_proxy_initcode = get_initcode("Proxy", [owner])

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
    get_initcode,
    owner,
    signature_of_owner_on_implementation,
):
    """Test that the proxy has proper value for implementation and owner address"""
    identity_proxy_initcode = get_initcode("Proxy", [owner])

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
    get_initcode,
    owner,
    signature_of_not_owner_on_implementation,
):
    """Tests that attempting to deploy a proxy with a wrong signature will fail"""
    constructor_args = [owner]
    identity_proxy_initcode = get_initcode("Proxy", constructor_args)

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


def test_clientlib_calculate_proxy_address(proxy_factory, get_initcode, owner):
    """Give out some tests values for pre calculating the proxy address in the clientlib tests"""
    identity_proxy_initcode = get_initcode("Proxy", [owner])

    pre_computed_address = build_create2_address(
        proxy_factory.address, identity_proxy_initcode
    )

    assert pre_computed_address.hex() == "0xdc7249221e3a7e973a34f667bcdad301c6c667d7"
    assert proxy_factory.address == "0xF2E246BB76DF876Cef8b38ae84130F4F55De395b"
    assert owner == "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
    assert (
        identity_proxy_initcode
        == "0x608060405234801561001057600080fd5b506040516020806102788339810180604052602081101561003057600080fd5b5050610237806100416000396000f3fe6080604052600436106100295760003560e01c80635c60da1b1461005c578063d784d4261461008d575b600080546040516001600160a01b0390911691369082376000803683855af43d6000833e808015610058573d83f35b3d83fd5b34801561006857600080fd5b506100716100c2565b604080516001600160a01b039092168252519081900360200190f35b34801561009957600080fd5b506100c0600480360360208110156100b057600080fd5b50356001600160a01b03166100d1565b005b6000546001600160a01b031681565b6000546001600160a01b031661010e576000805473ffffffffffffffffffffffffffffffffffffffff19166001600160a01b03831617905561018f565b333014610166576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252603d8152602001806101cf603d913960400191505060405180910390fd5b6000805473ffffffffffffffffffffffffffffffffffffffff19166001600160a01b0383161790555b604080516001600160a01b038316815290517f11135eea714a7c1c3b9aebf3d31bbd295f7e7262960215e086849c191d45bddc9181900360200190a15056fe54686520696d706c656d656e746174696f6e2063616e206f6e6c79206265206368616e6765642062792074686520636f6e747261637420697473656c66a165627a7a723058204f03c65132b7f67ed08ea73c5c83a4345aadcd408a5247bd471e03b5701f8ee500290000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf"  # noqa: E501
    )


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
    get_initcode,
):
    proxy = deploy_proxied_identity(
        web3,
        proxy_factory.address,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    )

    identity_proxy_initcode = get_initcode("Proxy", [owner])
    pre_computed_address = build_create2_address(
        proxy_factory.address, identity_proxy_initcode
    )

    assert proxy.address == pre_computed_address
    assert proxy.functions.implementation().call() == identity_implementation.address
