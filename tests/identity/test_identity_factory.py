import pytest

from web3 import Web3

from tldeploy.identity import MetaTransaction, Identity, get_pinned_proxy_interface
from eth_tester.exceptions import TransactionFailed

from tldeploy.identity import deploy_proxied_identity, build_create2_address

from deploy_tools.compile import build_initcode


def sign_implementation(
    proxy_factory_address, identity_implementation_address, owner_key
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    to_hash = ["0x19", "0x00", proxy_factory_address, identity_implementation_address]
    to_sign = Web3.solidityKeccak(abi_types, to_hash)
    return owner_key.sign_msg_hash(to_sign).to_bytes()


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[5]


@pytest.fixture(scope="session")
def owner_key(account_keys):
    return account_keys[5]


@pytest.fixture(scope="session")
def signature_of_owner_on_implementation(
    owner_key, identity_implementation, proxy_factory
):
    return sign_implementation(
        proxy_factory.address, identity_implementation.address, owner_key
    )


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
def signature_of_not_owner_on_implementation(
    account_keys, identity_implementation, proxy_factory
):
    return sign_implementation(
        proxy_factory.address, identity_implementation.address, account_keys[2]
    )


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


def test_build_create2_address_conform_to_EIP1014():
    """
    Tests out two examples given in https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1014.md
    """
    assert (
        build_create2_address("0x0000000000000000000000000000000000000000", "0x00")
        == "0x4D1A2e2bB4F88F0250f26Ffff098B0b30B26BF38"
    )
    assert (
        build_create2_address(
            Web3.toChecksumAddress("0x00000000000000000000000000000000deadbeef"),
            "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "0x00000000000000000000000000000000000000000000000000000000cafebabe",
        )
        == "0x1d8bfDC5D46DC4f61D6b6115972536eBE6A8854C"
    )


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

    assert identity_proxy_address == pre_computed_address


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
    function_call = proxied_identity.contract.functions.changeImplementation(
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


def test_clientlib_calculate_proxy_address(proxy_factory, get_proxy_initcode):
    """Give out some tests values for pre calculating the proxy address in the clientlib tests"""

    owner = "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
    identity_proxy_initcode = get_proxy_initcode([owner])

    assert proxy_factory.address == "0x8688966AE53807c273D8B9fCcf667F0A0a91b1d3"

    pre_computed_address = build_create2_address(
        proxy_factory.address, identity_proxy_initcode
    )
    assert pre_computed_address == "0x7025175Ac3537be29f764bbeAB26d5f89b0F49aC"


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


def remove_meta_data_hash(bytecode):
    # According to https://solidity.readthedocs.io/en/v0.5.8/metadata.html?highlight=metadata
    # the length of the meta data is 43 bytes
    return bytecode[: -43 * 2]


def test_correct_proxy_pinned(contract_assets):
    """Test that the pinned proxy is the correct one.
    Changes to the proxy contract will require to update the pinned proxy contract"""
    assert remove_meta_data_hash(
        contract_assets["Proxy"]["bytecode"]
    ) == remove_meta_data_hash(get_pinned_proxy_interface()["bytecode"])
