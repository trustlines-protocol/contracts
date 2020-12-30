#! pytest

import pytest

from deploy_tools import deploy_compiled_contract


@pytest.fixture(scope="session")
def upgradeable_implementation(deploy_contract):
    return deploy_contract(contract_identifier="TestUpgradeable")


@pytest.fixture(scope="session")
def upgraded_implementation(deploy_contract):
    return deploy_contract(contract_identifier="TestUpgraded")


@pytest.fixture(scope="session")
def proxy_beacon(owner_key, contract_assets, web3, upgradeable_implementation):
    return deploy_compiled_contract(
        abi=contract_assets["ProxyBeacon"]["abi"],
        bytecode=contract_assets["ProxyBeacon"]["bytecode"],
        constructor_args=(upgradeable_implementation.address,),
        web3=web3,
        private_key=owner_key,
    )


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def owner_key(account_keys):
    return account_keys[0]


@pytest.fixture(scope="session")
def not_owner(accounts, owner):
    not_owner = accounts[1]
    assert not_owner != owner
    return not_owner
