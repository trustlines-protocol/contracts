import json

from tlcontracts.deploy import deploy_networks


def main():
    chain_name = "testrpclocal"
    
    networks = [("Euro", "EUR", 2), ("US Dollar", "USD", 2), ("Testcoin", "T", 6)]
    
    networks, exchange, unw_eth = deploy_networks(chain_name, networks)

    addresses = dict()
    addresses['networks'] = [network.address for network in networks]
    addresses['exchange'] = exchange.address
    addresses['unwEth'] = unw_eth.address

    with open('addresses.json', 'w') as outfile:
        json.dump(addresses, outfile)

    # small test if deployment worked
    assert networks[0].call().name() == 'Euro'
    assert unw_eth.call().name() == 'Unwrapping Ether'
    
    
if __name__ == "__main__":
    main()
