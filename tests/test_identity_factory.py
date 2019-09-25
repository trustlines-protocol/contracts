import pytest

from web3 import Web3
from hexbytes import HexBytes

from web3._utils.abi import get_constructor_abi
from web3._utils.contracts import encode_abi
from tldeploy.identity import MetaTransaction, Identity, Delegate
from eth_tester.exceptions import TransactionFailed


def build_create2_address(
    deployer_address,
    bytecode,
    salt="0x0000000000000000000000000000000000000000000000000000000000000000",
):
    hashed_bytecode = Web3.solidityKeccak(["bytes"], [bytecode])
    to_hash = ["0xff", deployer_address, salt, hashed_bytecode]
    abi_types = ["bytes1", "address", "bytes32", "bytes32"]

    return Web3.solidityKeccak(abi_types, to_hash)[12:]


@pytest.fixture(scope="session")
def identity_factory(deploy_contract, web3):

    identity_factory = deploy_contract("IdentityFactory")
    return identity_factory


@pytest.fixture(scope="session")
def identity_implementation(deploy_contract, web3):

    identity_implementation = deploy_contract("Identity")
    return identity_implementation


@pytest.fixture(scope="session")
def identity_implementation_different_address(deploy_contract, web3):

    identity_implementation = deploy_contract("Identity")
    return identity_implementation


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def owner_key(account_keys):
    return account_keys[0]


@pytest.fixture(scope="session")
def signature_of_owner_on_implementation(
    owner_key, identity_implementation, identity_factory
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    to_hash = [
        "0x19",
        "0x00",
        identity_factory.address,
        identity_implementation.address,
    ]
    to_sign = Web3.solidityKeccak(abi_types, to_hash)
    return owner_key.sign_msg_hash(to_sign).to_bytes()


@pytest.fixture(scope="session")
def signature_of_not_owner_on_implementation(
    account_keys, identity_implementation, identity_factory
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    to_hash = [
        "0x19",
        "0x00",
        identity_factory.address,
        identity_implementation.address,
    ]
    to_sign = Web3.solidityKeccak(abi_types, to_hash)
    return account_keys[2].sign_msg_hash(to_sign).to_bytes()


@pytest.fixture(scope="session")
def build_initcode(contract_assets):
    """
    should be imported from deploy-tools in the long run, actually cannot import from cli.py, need to refactor
    """

    def initcode(contract_name, args):
        abi = contract_assets[contract_name]["abi"]
        bytecode = contract_assets[contract_name]["bytecode"]
        constructor_abi = get_constructor_abi(abi)

        # The initcode is the bytecode with the encoded arguments appended
        if constructor_abi:
            return encode_abi(
                web3=None, abi=constructor_abi, arguments=args, data=bytecode
            )
        else:
            return bytecode

    return initcode


@pytest.fixture()
def proxied_identity_contract_with_owner(
    identity_factory,
    identity_implementation,
    build_initcode,
    owner,
    signature_of_owner_on_implementation,
    web3,
    contract_assets,
):
    constructor_args = [owner]
    identity_proxy_initcode = build_initcode("IdentityProxy", constructor_args)

    proxy_address = build_create2_address(
        identity_factory.address, identity_proxy_initcode
    )

    identity_factory.functions.deployProxy(
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
def proxied_contract_with_owner(
    proxied_identity_contract_with_owner, web3, contract_assets
):

    contract = web3.eth.contract(
        address=proxied_identity_contract_with_owner.address,
        abi=contract_assets["IdentityProxy"]["abi"],
        bytecode=contract_assets["IdentityProxy"]["bytecode"],
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
    identity_factory,
    identity_implementation,
    build_initcode,
    owner,
    signature_of_owner_on_implementation,
):
    """Test that we can deploy the proxy at a pre-computed address"""
    constructor_args = [owner]
    identity_proxy_initcode = build_initcode("IdentityProxy", constructor_args)

    pre_computed_address = build_create2_address(
        identity_factory.address, identity_proxy_initcode
    )

    identity_factory.functions.deployProxy(
        identity_proxy_initcode,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    ).transact()
    deployed_event = identity_factory.events.DeployedProxy.getLogs()[0]
    identity_proxy_address = deployed_event["args"]["proxyAddress"]

    assert HexBytes(identity_proxy_address) == pre_computed_address


def test_proxy_deployment_arguments(
    identity_factory,
    web3,
    contract_assets,
    identity_implementation,
    build_initcode,
    owner,
    signature_of_owner_on_implementation,
):
    """Test that the proxy has proper value for IdentityImplementation and owner address"""
    constructor_args = [owner]
    identity_proxy_initcode = build_initcode("IdentityProxy", constructor_args)

    identity_factory.functions.deployProxy(
        identity_proxy_initcode,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    ).transact()

    deployed_event = identity_factory.events.DeployedProxy.getLogs()[0]
    identity_proxy_address = deployed_event["args"]["proxyAddress"]

    identity_proxy_contract = web3.eth.contract(
        address=identity_proxy_address,
        abi=contract_assets["IdentityProxy"]["abi"],
        bytecode=contract_assets["IdentityProxy"]["bytecode"],
    )
    proxied_identity_contract = web3.eth.contract(
        address=identity_proxy_address,
        abi=contract_assets["Identity"]["abi"],
        bytecode=contract_assets["Identity"]["bytecode"],
    )

    identity_implementation_address = (
        identity_proxy_contract.functions.identityImplementation().call()
    )

    assert identity_implementation_address == identity_implementation.address
    assert proxied_identity_contract.functions.owner().call() == owner


def test_deploy_proxy_wrong_signature(
    identity_factory,
    identity_implementation,
    build_initcode,
    owner,
    signature_of_not_owner_on_implementation,
):
    """Tests that attempting to deploy a proxy with a wrong signature will fail"""
    constructor_args = [owner]
    identity_proxy_initcode = build_initcode("IdentityProxy", constructor_args)

    with pytest.raises(TransactionFailed):
        identity_factory.functions.deployProxy(
            identity_proxy_initcode,
            identity_implementation.address,
            signature_of_not_owner_on_implementation,
        ).transact()


def test_change_identity_implementation(
    web3,
    proxied_contract_with_owner,
    identity_implementation,
    identity_implementation_different_address,
    proxied_identity,
    delegate,
):

    assert (
        proxied_contract_with_owner.functions.identityImplementation().call()
        == identity_implementation.address
    )

    # TODO: check why identity does not like addresses as hexbytes
    to = proxied_contract_with_owner.address
    function_call = proxied_contract_with_owner.functions.setImplementation(
        identity_implementation_different_address.address
    )

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    meta_transaction = proxied_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    delegate.send_signed_meta_transaction(meta_transaction)

    assert (
        proxied_contract_with_owner.functions.identityImplementation().call()
        == identity_implementation_different_address.address
    )
    assert (
        proxied_contract_with_owner.functions.identityImplementation().call()
        != identity_implementation.address
    )
