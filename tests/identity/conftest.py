import pytest
from deploy_tools import deploy_compiled_contract
from tldeploy.identity import Delegate, Identity, deploy_proxied_identity
from web3 import Web3

from tldeploy.core import get_chain_id


@pytest.fixture(scope="session")
def chain_id(web3):
    return get_chain_id(web3)


@pytest.fixture(scope="session")
def proxy_factory(deploy_contract, contract_assets, web3, chain_id):
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
        constructor_args=(chain_id,),
        web3=web3,
        private_key=new_account.key,
    )

    return proxy_factory


@pytest.fixture(scope="session")
def identity_implementation(deploy_contract, web3):

    identity_implementation = deploy_contract("Identity")
    return identity_implementation


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def owner_key(account_keys):
    return account_keys[0]


@pytest.fixture(scope="session")
def delegate_address(accounts):
    return accounts[1]


@pytest.fixture(scope="session")
def delegate(contract_assets, delegate_address, web3):
    return Delegate(
        delegate_address,
        web3=web3,
        identity_contract_abi=contract_assets["Identity"]["abi"],
        # This forces eth-tester to do gas estimation and so raise Transaction failed
        default_gas=None,
    )


@pytest.fixture(scope="session")
def identity_contract(deploy_contract, web3, owner, chain_id):

    identity_contract = deploy_contract("Identity")
    identity_contract.functions.init(owner, chain_id).transact({"from": owner})
    web3.eth.sendTransaction(
        {"to": identity_contract.address, "from": owner, "value": 1000000}
    )
    return identity_contract


@pytest.fixture(scope="session")
def identity(identity_contract, owner_key):
    return Identity(contract=identity_contract, owner_private_key=owner_key)


@pytest.fixture(scope="session")
def signature_of_owner_on_implementation(
    owner_key, identity_implementation, proxy_factory
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    to_hash = ["0x19", "0x00", proxy_factory.address, identity_implementation.address]
    to_sign = Web3.solidityKeccak(abi_types, to_hash)
    return owner_key.sign_msg_hash(to_sign).to_bytes()


@pytest.fixture()
def proxied_identity_contract(
    web3,
    proxy_factory,
    identity_implementation,
    signature_of_owner_on_implementation,
    owner,
):
    proxied_identity_contract = deploy_proxied_identity(
        web3=web3,
        factory_address=proxy_factory.address,
        implementation_address=identity_implementation.address,
        signature=signature_of_owner_on_implementation,
    )

    web3.eth.sendTransaction(
        {"to": proxied_identity_contract.address, "from": owner, "value": 1000000}
    )
    return proxied_identity_contract


@pytest.fixture()
def proxied_identity(proxied_identity_contract, owner_key):
    return Identity(contract=proxied_identity_contract, owner_private_key=owner_key)
