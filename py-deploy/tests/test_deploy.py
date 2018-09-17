from tldeploy.core import deploy_networks, deploy_network


def test_deploy_networks(web3):
    networks = [("Fugger", "FUG", 2), ("Hours", "HOU", 2), ("Testcoin", "T", 6)]
    networks, exchange, unw_eth = deploy_networks(web3, networks)

    assert networks[0].call().name() == "Fugger"
    assert unw_eth.call().decimals() == 18


def test_deploy_network(web3):
    network = deploy_network(web3, "Testcoin", "T", 2)

    assert network.call().name() == "Testcoin"
