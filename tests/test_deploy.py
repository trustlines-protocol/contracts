#! pytest

from tldeploy.core import deploy_networks, deploy_network


def test_deploy_networks(web3):
    example_settings = [
        {
            "name": "Test",
            "symbol": "TST",
            "decimals": 4,
            "fee_divisor": 1000,
            "default_interest_rate": 0,
            "custom_interests": True,
        },
        {
            "name": "Test Coin",
            "symbol": "TCN",
            "decimals": 2,
            "fee_divisor": 0,
            "default_interest_rate": 1000,
            "custom_interests": False,
        },
    ]
    networks, exchange, unw_eth = deploy_networks(web3, example_settings)

    assert networks[0].functions.name().call() == "Test"
    assert networks[0].functions.symbol().call() == "TST"
    assert networks[1].functions.decimals().call() == 2
    assert unw_eth.functions.decimals().call() == 18


def test_deploy_network(web3):
    network = deploy_network(
        web3,
        name="Testcoin",
        symbol="T",
        decimals=2,
        fee_divisor=100,
        default_interest_rate=100,
        custom_interests=False,
        prevent_mediator_interests=False,
        set_account_enabled=True,
    )

    assert network.functions.name().call() == "Testcoin"
    assert network.functions.symbol().call() == "T"
    assert network.functions.decimals().call() == 2
    assert network.functions.customInterests().call() is False
    assert network.functions.defaultInterestRate().call() == 100
    assert network.functions.accountManagementEnabled().call() is True
