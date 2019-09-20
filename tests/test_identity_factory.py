import pytest

from web3 import Web3
from hexbytes import HexBytes

from web3._utils.abi import get_constructor_abi
from web3._utils.contracts import encode_abi


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
def owner(accounts):
    return accounts[0]


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


def test_deploy_identity_proxy_at_precomputed_address(
    identity_factory, identity_implementation, build_initcode
):
    """Test that we can deploy the proxy at a pre-computed address"""
    constructor_args = [identity_implementation.address]
    identity_proxy_initcode = build_initcode("IdentityProxy", constructor_args)

    pre_computed_address = build_create2_address(
        identity_factory.address, identity_proxy_initcode
    )

    identity_factory.functions.deployProxy(identity_proxy_initcode).transact()
    deployed_event = identity_factory.events.DeployedProxy.getLogs()[0]
    identity_proxy_address = deployed_event["args"]["proxyAddress"]

    assert HexBytes(identity_proxy_address) == pre_computed_address


def test_proxy_bound_to_proper_implementation(
    identity_factory, web3, contract_assets, identity_implementation, build_initcode
):
    """Test that the proxy has proper value for IdentityImplementation address"""
    constructor_args = [identity_implementation.address]
    identity_proxy_initcode = build_initcode("IdentityProxy", constructor_args)

    identity_factory.functions.deployProxy(identity_proxy_initcode).transact()

    deployed_event = identity_factory.events.DeployedProxy.getLogs()[0]
    identity_proxy_address = deployed_event["args"]["proxyAddress"]

    identity_proxy_contract = web3.eth.contract(
        address=identity_proxy_address,
        abi=contract_assets["IdentityProxy"]["abi"],
        bytecode=contract_assets["IdentityProxy"]["bytecode"],
    )

    identity_implementation_address = (
        identity_proxy_contract.functions.identityImplementation().call()
    )
    assert identity_implementation_address == identity_implementation.address


def test_init_identity_via_proxy(
    web3,
    identity_factory,
    build_initcode,
    identity_implementation,
    owner,
    contract_assets,
):
    constructor_args = [identity_implementation.address]
    identity_proxy_initcode = build_initcode("IdentityProxy", constructor_args)

    identity_factory.functions.deployProxy(identity_proxy_initcode).transact()

    deployed_event = identity_factory.events.DeployedProxy.getLogs()[0]
    identity_proxy_address = deployed_event["args"]["proxyAddress"]

    proxied_identity_contract = web3.eth.contract(
        address=identity_proxy_address,
        abi=contract_assets["Identity"]["abi"],
        bytecode=contract_assets["Identity"]["bytecode"],
    )
    proxied_identity_contract.functions.init(owner).transact()
    proxy_owner = proxied_identity_contract.functions.owner().call()

    assert proxy_owner == owner
