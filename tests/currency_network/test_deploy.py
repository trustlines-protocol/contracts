#! pytest
import pytest

from tests.currency_network.conftest import ADDRESS_0
from tldeploy.core import (
    deploy_networks,
    deploy_network,
    deploy_beacon,
    deploy_currency_network_proxy,
    verify_owner_not_deployer,
    deploy_and_migrate_network,
    NetworkSettings,
)

from tests.conftest import EXPIRATION_TIME, NETWORK_SETTINGS


def test_deploy_networks(web3):
    example_settings = [
        NetworkSettings(
            name="Test",
            symbol="TST",
            decimals=4,
            fee_divisor=1000,
            default_interest_rate=0,
            custom_interests=True,
            expiration_time=EXPIRATION_TIME,
            prevent_mediator_interests=False,
        ),
        NetworkSettings(
            name="Test Coin",
            symbol="TCN",
            decimals=2,
            fee_divisor=0,
            default_interest_rate=1000,
            custom_interests=False,
            expiration_time=0,
            prevent_mediator_interests=False,
        ),
    ]
    networks, exchange, unw_eth = deploy_networks(web3, example_settings)

    assert networks[0].functions.name().call() == "Test"
    assert networks[0].functions.symbol().call() == "TST"
    assert networks[1].functions.decimals().call() == 2
    assert unw_eth.functions.decimals().call() == 18


def test_deploy_network(web3):
    network = deploy_network(web3, NETWORK_SETTINGS)

    assert network.functions.name().call() == NETWORK_SETTINGS.name
    assert network.functions.symbol().call() == NETWORK_SETTINGS.symbol
    assert network.functions.decimals().call() == NETWORK_SETTINGS.decimals
    assert (
        network.functions.customInterests().call() == NETWORK_SETTINGS.custom_interests
    )
    assert (
        network.functions.defaultInterestRate().call()
        == NETWORK_SETTINGS.default_interest_rate
    )
    assert network.functions.expirationTime().call() == NETWORK_SETTINGS.expiration_time


def test_deploy_beacon(web3, accounts, currency_network_contract, account_keys):
    owner = accounts[0]
    implementation = currency_network_contract.address
    deployer_key = account_keys[1]

    beacon = deploy_beacon(
        web3=web3,
        implementation_address=implementation,
        owner_address=owner,
        private_key=deployer_key,
    )

    assert beacon.functions.owner().call() == owner
    assert beacon.functions.implementation().call() == implementation


def test_deploy_currency_network_proxy(
    web3, beacon_with_currency_network, accounts, account_keys, contract_assets
):
    owner = accounts[0]
    deployer = accounts[1]
    deployer_key = account_keys[1]

    proxied_currency_network = deploy_currency_network_proxy(
        web3=web3,
        network_settings=NETWORK_SETTINGS,
        beacon_address=beacon_with_currency_network.address,
        owner_address=owner,
        private_key=deployer_key,
    )
    proxy = web3.eth.contract(
        address=proxied_currency_network.address,
        abi=contract_assets["AdministrativeProxy"]["abi"],
    )

    assert proxy.functions.admin().call({"from": owner}) == owner
    assert (
        proxy.functions.beacon().call({"from": owner})
        == beacon_with_currency_network.address
    )
    assert (
        proxied_currency_network.functions.name().call({"from": deployer})
        == NETWORK_SETTINGS.name
    )
    assert (
        proxied_currency_network.functions.symbol().call({"from": deployer})
        == NETWORK_SETTINGS.symbol
    )
    assert (
        proxied_currency_network.functions.decimals().call({"from": deployer})
        == NETWORK_SETTINGS.decimals
    )
    assert (
        proxied_currency_network.functions.customInterests().call({"from": deployer})
        == NETWORK_SETTINGS.custom_interests
    )
    assert (
        proxied_currency_network.functions.defaultInterestRate().call(
            {"from": deployer}
        )
        == NETWORK_SETTINGS.default_interest_rate
    )
    assert (
        proxied_currency_network.functions.expirationTime().call({"from": deployer})
        == NETWORK_SETTINGS.expiration_time
    )


def test_verify_owner_not_deployer_default_account(web3, accounts):
    with pytest.raises(ValueError):
        # This is the address used by eth_tester by default for transactions
        default_address = accounts[0]
        verify_owner_not_deployer(web3, owner_address=default_address, private_key=None)


def test_verify_owner_not_deployer_private_key(web3, accounts, account_keys):
    with pytest.raises(ValueError):
        verify_owner_not_deployer(
            web3, owner_address=accounts[0], private_key=account_keys[0]
        )


def test_deploy_and_migrate_network(
    web3,
    beacon_with_currency_network,
    currency_network_contract_with_trustlines,
    owner,
    not_owner_key,
    chain,
):
    # The migration requires that the old currency network is expired
    expiration_time = (
        currency_network_contract_with_trustlines.functions.expirationTime().call()
    )
    chain.time_travel(expiration_time + 1)
    chain.mine_block()
    deploy_and_migrate_network(
        web3_source=web3,
        web3_dest=web3,
        beacon_address=beacon_with_currency_network.address,
        owner_address=owner,
        master_copy_address=ADDRESS_0,
        proxy_factory_address=ADDRESS_0,
        old_network=currency_network_contract_with_trustlines,
        private_key=not_owner_key,
    )
