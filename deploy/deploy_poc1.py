from tlcontracts.deploy import deploy_networks


def main():
    chain_name = "dockerrpc"

    networks = [("Fugger", "FUG", 2), ("Hours", "HOU", 2)]

    networks, exchange, unw_eth = deploy_networks(chain_name, networks)

    addresses = dict()
    addresses['networks'] = [network.address for network in networks]
    addresses['exchange'] = exchange.address
    addresses['unwEth'] = unw_eth.address

    print(addresses)

    # small test if deployment worked
    assert networks[0].call().decimals() == 2
    assert unw_eth.call().decimals() == 18


if __name__ == "__main__":
    main()
