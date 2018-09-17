#! pytest

from tldeploy.core import deploy_networks, deploy_network


def test_deploy_networks(web3):
    networks = [("Fugger", "FUG", 2), ("Hours", "HOU", 2), ("Testcoin", "T", 6)]
    networks, exchange, unw_eth = deploy_networks(web3, networks)

    assert networks[0].functions.name().call() == "Fugger"
    assert unw_eth.functions.decimals().call() == 18


def test_deploy_network(web3):
    network = deploy_network(web3, "Testcoin", "T", 2)

    assert network.functions.name().call() == "Testcoin"
