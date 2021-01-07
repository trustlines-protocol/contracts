#! pytest

from tldeploy.core import deploy_networks, deploy_network

from tests.conftest import EXPIRATION_TIME, NETWORK_SETTINGS


def test_deploy_networks(web3):
    example_settings = [
        {
            "name": "Test",
            "symbol": "TST",
            "decimals": 4,
            "fee_divisor": 1000,
            "default_interest_rate": 0,
            "custom_interests": True,
            "expiration_time": EXPIRATION_TIME,
            "prevent_mediator_interests": False,
        },
        {
            "name": "Test Coin",
            "symbol": "TCN",
            "decimals": 2,
            "fee_divisor": 0,
            "default_interest_rate": 1000,
            "custom_interests": False,
            "expiration_time": EXPIRATION_TIME,
            "prevent_mediator_interests": False,
        },
    ]
    networks, exchange, unw_eth = deploy_networks(web3, example_settings)

    assert networks[0].functions.name().call() == "Test"
    assert networks[0].functions.symbol().call() == "TST"
    assert networks[1].functions.decimals().call() == 2
    assert unw_eth.functions.decimals().call() == 18


def test_deploy_network(web3):
    network = deploy_network(web3, NETWORK_SETTINGS)

    assert network.functions.name().call() == NETWORK_SETTINGS["name"]
    assert network.functions.symbol().call() == NETWORK_SETTINGS["symbol"]
    assert network.functions.decimals().call() == NETWORK_SETTINGS["decimals"]
    assert (
        network.functions.customInterests().call()
        == NETWORK_SETTINGS["custom_interests"]
    )
    assert (
        network.functions.defaultInterestRate().call()
        == NETWORK_SETTINGS["default_interest_rate"]
    )
    assert (
        network.functions.expirationTime().call() == NETWORK_SETTINGS["expiration_time"]
    )
