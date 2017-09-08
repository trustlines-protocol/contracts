"""Deploy Edgeless token and smart contract in testnet.
A simple Python script to deploy contracts and then do a smoke test for them.
"""
from populus import Project
from populus.utils.wait import wait_for_transaction_receipt
from web3 import Web3
from web3.utils.compat import (
    Timeout,
)


def check_successful_tx(web3: Web3, txid: str, timeout=180) -> dict:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt
    """
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    txinfo = web3.eth.getTransaction(txid)
    assert txinfo["gas"] != receipt["gasUsed"]
    print("gas used: ", receipt["gasUsed"])
    return receipt


def wait(transfer_filter):
    with Timeout(30) as timeout:
        while not transfer_filter.get(False):
            timeout.sleep(2)


def deploy(contract_name, chain, *args):
    contract = chain.provider.get_contract_factory(contract_name)
    txhash = contract.deploy(args=args)
    receipt = check_successful_tx(chain.web3, txhash)
    id_address = receipt["contractAddress"]
    print(contract_name, "contract address is", id_address)
    return contract(id_address)


def main():
    project = Project('populus.json')
    chain_name = "testrpclocal"
    print("Make sure {} chain is running, you can connect to it, or you'll get timeout".format(chain_name))

    with project.get_chain(chain_name) as chain:
        web3 = chain.web3

    print("Web3 provider is", web3.currentProvider)
    registry = deploy("Registry", chain)
    currencyNetworkFactory = deploy("CurrencyNetworkFactory", chain, registry.address)
    transfer_filter = currencyNetworkFactory.on("CurrencyNetworkCreated")
    txid = currencyNetworkFactory.transact({"from": web3.eth.accounts[0]}).CreateCurrencyNetwork('Trustlines', 'T', web3.eth.accounts[0], 1000, 100, 25, 100);
    receipt = check_successful_tx(web3, txid)
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    addr_trustlines = log_entries[0]['args']['_currencyNetworkContract']
    print("REAL CurrencyNetwork contract address is", addr_trustlines)

    resolver = deploy("Resolver", chain, addr_trustlines)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getAccountExt(address,address)", "getAccountExtLen()", addr_trustlines);
    receipt = check_successful_tx(web3, txid)
    transfer_filter = resolver.on("FallbackChanged")
    proxy = deploy("EtherRouter", chain, resolver.address)
    proxied_trustlines = chain.provider.get_contract_factory("CurrencyNetwork")(proxy.address)
    txid = proxied_trustlines.transact({"from": web3.eth.accounts[0]}).setAccount(web3.eth.accounts[6], web3.eth.accounts[7], 2000000, 1, 1, 1, 1, 1, 1, 1);
    receipt = check_successful_tx(web3, txid)
    print(proxied_trustlines.call().getAccountExt(web3.eth.accounts[6], web3.eth.accounts[7]))

    storagev2 = deploy("CurrencyNetwork", chain)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).setFallback(storagev2.address);
    receipt = check_successful_tx(web3, txid)
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    print("Forwarded to ", log_entries[0]['args']['newFallback'])
    txid = proxied_trustlines.transact({"from": web3.eth.accounts[0]}).init('Trustlines', 'T', 1000, 100, 25, 100)
    receipt = check_successful_tx(web3, txid)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getAccountExt(address,address)", "getAccountExtLen()", storagev2.address);
    receipt = check_successful_tx(web3, txid)
    print(proxied_trustlines.call().getAccountExt(web3.eth.accounts[6], web3.eth.accounts[7]))


if __name__ == "__main__":
    main()
