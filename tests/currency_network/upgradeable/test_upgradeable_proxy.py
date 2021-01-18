from deploy_tools import deploy_compiled_contract
import pytest

from tests.conftest import get_single_event_of_contract


# Constants matching the version returned by `version()` on the test upgradeable and upgraded contracts
UPGRADEABLE_VERSION = 1
UPGRADED_VERSION = 2


@pytest.fixture(scope="session")
def proxy(
    owner_key,
    contract_assets,
    web3,
    upgradeable_implementation,
    upgradeable_initialized_value,
    proxy_beacon,
):
    implementation_init_data = upgradeable_implementation.encodeABI(
        "init", (upgradeable_initialized_value,)
    )
    return deploy_compiled_contract(
        abi=contract_assets["AdministrativeProxy"]["abi"],
        bytecode=contract_assets["AdministrativeProxy"]["bytecode"],
        constructor_args=(proxy_beacon.address, implementation_init_data),
        web3=web3,
        private_key=owner_key,
    )


@pytest.fixture(scope="session")
def new_proxy_beacon(owner_key, contract_assets, web3, upgraded_implementation):
    return deploy_compiled_contract(
        abi=contract_assets["ProxyBeacon"]["abi"],
        bytecode=contract_assets["ProxyBeacon"]["bytecode"],
        constructor_args=(upgraded_implementation.address,),
        web3=web3,
        private_key=owner_key,
    )


@pytest.fixture(scope="session")
def upgradeable_initialized_value():
    """Arbitrary value used to test the init function of upgradeable contract"""
    return 123


@pytest.fixture(scope="session")
def upgraded_initialized_value(upgradeable_initialized_value):
    """Arbitrary value used to test the init function of upgraded contract,
    differs from the value of upgradeable contract"""
    value = 456
    assert value != upgradeable_initialized_value
    return value


@pytest.fixture(scope="session")
def proxied_upgradeable_contract(proxy, contract_assets, web3):
    return web3.eth.contract(
        abi=contract_assets["TestUpgradeable"]["abi"],
        bytecode=contract_assets["TestUpgradeable"]["bytecode"],
        address=proxy.address,
    )


@pytest.fixture(scope="session")
def proxied_upgraded_contract(proxy, contract_assets, web3):
    return web3.eth.contract(
        abi=contract_assets["TestUpgraded"]["abi"],
        bytecode=contract_assets["TestUpgraded"]["bytecode"],
        address=proxy.address,
    )


def test_proxy_admin(proxy, owner):
    assert proxy.functions.admin().call({"from": owner}) == owner


def test_get_admin_not_admin(proxy, not_owner):
    assert proxy.functions.admin().call({"from": not_owner}) == proxy.address


def test_get_beacon(proxy, owner, proxy_beacon):
    assert proxy.functions.beacon().call({"from": owner}) == proxy_beacon.address


def test_get_beacon_not_admin(proxy, not_owner, assert_failing_call):
    assert_failing_call(proxy.functions.beacon(), {"from": not_owner})


def test_get_implementation(proxy, owner, upgradeable_implementation):
    assert (
        proxy.functions.implementation().call({"from": owner})
        == upgradeable_implementation.address
    )


def test_get_implementation_not_admin(proxy, not_owner, assert_failing_call):
    assert_failing_call(proxy.functions.implementation(), {"from": not_owner})


def test_call_proxied_function(proxied_upgradeable_contract, not_owner):
    value = 123
    proxied_upgradeable_contract.functions.setTestValue(value).transact(
        {"from": not_owner}
    )
    assert (
        proxied_upgradeable_contract.functions.testValue().call({"from": not_owner})
        == value
    )


def test_call_proxied_function_admin(
    proxied_upgradeable_contract, owner, assert_failing_transaction
):
    assert_failing_transaction(
        proxied_upgradeable_contract.functions.setTestValue(456), {"from": owner}
    )


def test_call_payable_proxied_function_admin(
    proxied_upgradeable_contract, owner, assert_failing_transaction
):
    assert_failing_transaction(
        proxied_upgradeable_contract.functions.setTestValue(456),
        {"from": owner, "value": 1},
    )


def test_call_proxied_init_value(
    proxied_upgradeable_contract, not_owner, upgradeable_initialized_value
):
    assert (
        proxied_upgradeable_contract.functions.initializedValue().call(
            {"from": not_owner}
        )
        == upgradeable_initialized_value
    )


def test_change_admin(proxy, not_owner, owner):
    proxy.functions.changeAdmin(not_owner).transact({"from": owner})
    assert proxy.functions.admin().call({"from": not_owner}) == not_owner


def test_change_admin_not_admin(proxy, not_owner, owner, assert_failing_transaction):
    assert_failing_transaction(proxy.functions.changeAdmin(owner), {"from": not_owner})


def test_change_admin_event(proxy, not_owner, owner):
    proxy.functions.changeAdmin(not_owner).transact({"from": owner})
    event = get_single_event_of_contract(proxy, "AdminChanged")
    assert event["args"]["previousAdmin"] == owner
    assert event["args"]["newAdmin"] == not_owner


def test_change_beacon(
    proxy,
    owner,
    new_proxy_beacon,
    not_owner,
    proxied_upgraded_contract,
    upgradeable_initialized_value,
):
    proxy.functions.changeBeacon(new_proxy_beacon.address).transact({"from": owner})
    assert proxy.functions.beacon().call({"from": owner}) == new_proxy_beacon.address
    assert (
        proxied_upgraded_contract.functions.version().call({"from": not_owner})
        == UPGRADED_VERSION
    )
    assert (
        proxied_upgraded_contract.functions.initializedValue().call({"from": not_owner})
        == upgradeable_initialized_value
    )


def test_change_beacon_not_admin(
    proxy, not_owner, new_proxy_beacon, assert_failing_transaction
):
    assert_failing_transaction(
        proxy.functions.changeBeacon(new_proxy_beacon.address), {"from": not_owner}
    )


def test_change_beacon_event(proxy, new_proxy_beacon, proxy_beacon, owner):
    proxy.functions.changeBeacon(new_proxy_beacon.address).transact({"from": owner})
    event = get_single_event_of_contract(proxy, "BeaconChanged")
    assert event["args"]["previousBeacon"] == proxy_beacon.address
    assert event["args"]["newBeacon"] == new_proxy_beacon.address


def test_change_beacon_and_call(
    proxy,
    owner,
    new_proxy_beacon,
    not_owner,
    proxied_upgraded_contract,
    upgraded_initialized_value,
):
    init_call = proxied_upgraded_contract.encodeABI(
        "init", (upgraded_initialized_value,)
    )
    proxy.functions.changeBeaconAndCall(new_proxy_beacon.address, init_call).transact(
        {"from": owner}
    )
    assert proxy.functions.beacon().call({"from": owner}) == new_proxy_beacon.address
    assert (
        proxied_upgraded_contract.functions.version().call({"from": not_owner})
        == UPGRADED_VERSION
    )
    assert (
        proxied_upgraded_contract.functions.initializedValue().call({"from": not_owner})
        == upgraded_initialized_value
    )


def test_change_beacon_and_call_not_admin(
    proxy,
    not_owner,
    proxied_upgraded_contract,
    new_proxy_beacon,
    upgraded_initialized_value,
    assert_failing_transaction,
):
    init_call = proxied_upgraded_contract.encodeABI(
        "init", (upgraded_initialized_value,)
    )
    assert_failing_transaction(
        proxy.functions.changeBeaconAndCall(new_proxy_beacon.address, init_call),
        {"from": not_owner},
    )


def test_change_beacon_and_call_event(
    proxy,
    owner,
    new_proxy_beacon,
    proxied_upgraded_contract,
    upgraded_initialized_value,
    proxy_beacon,
):
    init_call = proxied_upgraded_contract.encodeABI(
        "init", (upgraded_initialized_value,)
    )
    proxy.functions.changeBeaconAndCall(new_proxy_beacon.address, init_call).transact(
        {"from": owner}
    )
    event = get_single_event_of_contract(proxy, "BeaconChanged")
    assert event["args"]["previousBeacon"] == proxy_beacon.address
    assert event["args"]["newBeacon"] == new_proxy_beacon.address


def test_change_implementation_in_beacon(
    proxy,
    proxy_beacon,
    upgraded_implementation,
    owner,
    not_owner,
    proxied_upgraded_contract,
    upgradeable_initialized_value,
):
    proxy_beacon.functions.upgradeTo(upgraded_implementation.address).transact(
        {"from": owner}
    )

    assert (
        proxy.functions.implementation().call({"from": owner})
        == upgraded_implementation.address
    )
    assert (
        proxied_upgraded_contract.functions.version().call({"from": not_owner})
        == UPGRADED_VERSION
    )
    assert (
        proxied_upgraded_contract.functions.initializedValue().call({"from": not_owner})
        == upgradeable_initialized_value
    )
