from populus import Project


from tlcontracts.deploy import deploy_test_networks


def main():
    chain_name = "dockerrpc"
    
    networks = [("Euro", "EUR", 2), ("US Dollar", "USD", 2), ("Testcoin", "T", 6)]
    
    network_addresses = deploy_test_networks(chain_name, networks)
    
    with open("networks", 'w') as file_handler:
        for network_address in network_addresses:
            file_handler.write("{}\n".format(network_address))
    
    
if __name__ == "__main__":
    main()
