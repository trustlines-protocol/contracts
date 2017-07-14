"""Deploy Edgeless token and smart contract in testnet.
A simple Python script to deploy contracts and then do a smoke test for them.
"""
from populus import Project
from populus.utils.wait import wait_for_transaction_receipt
from web3 import Web3
from web3.utils.compat import (
    Timeout,
)

trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, tlAB, tlBA)

def trustlines_contract(trustlines_contract, tlAddr0, tlAddr1, proxy0, proxy1, web3):
    for (A, B, tlAB, tlBA) in trustlines:
        print((A, B, tlAB, tlBA))
        txid = trustlines_contract(tlAddr0).transact({"from":web3.eth.accounts[A]}).updateCreditline(proxy1, tlAB)
        receipt = check_succesful_tx(web3, txid)
        txid = trustlines_contract(tlAddr1).transact({"from":web3.eth.accounts[B]}).acceptCreditline(proxy0, tlAB)
        receipt = check_succesful_tx(web3, txid)
        txid = trustlines_contract(tlAddr1).transact({"from":web3.eth.accounts[B]}).updateCreditline(proxy0, tlBA)
        receipt = check_succesful_tx(web3, txid)
        txid = trustlines_contract(tlAddr0).transact({"from":web3.eth.accounts[A]}).acceptCreditline(proxy1, tlBA)
    receipt = check_succesful_tx(web3, txid)
    return trustlines_contract

def check_succesful_tx(web3: Web3, txid: str, timeout=180) -> dict:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt
    """
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    txinfo = web3.eth.getTransaction(txid)
    assert txinfo["gas"] != receipt["gasUsed"]
    return receipt

def wait(transfer_filter):
    with Timeout(30) as timeout:
        while not transfer_filter.get(False):
            timeout.sleep(2)

def deploy(contract_name, chain, *args):
    contract = chain.provider.get_contract_factory(contract_name)
    txhash = contract.deploy(args=args)
    receipt = check_succesful_tx(chain.web3, txhash)
    id_address = receipt["contractAddress"]
    print(contract_name, " contract address is", id_address)
    return contract(id_address)

def main():
    project = Project()
    chain_name = "testrpclocal"
    print("Make sure {} chain is running, you can connect to it, or you'll get timeout".format(chain_name))

    with project.get_chain(chain_name) as chain:
        web3 = chain.web3

    print("Web3 provider is", web3.currentProvider)
    eternalStorage = deploy("EternalStorage", chain)
    currencyNetwork = deploy("CurrencyNetwork", chain, 'Trustlines', 'T', eternalStorage.address)
    idFactory = deploy("IdentityFactoryWithRecoveryKey", chain)
    transfer_filter = idFactory.on('IdentityCreated')

    # create 1st identity
    txhash = idFactory.transact().CreateProxyWithControllerAndRecoveryKey(currencyNetwork.address, web3.eth.accounts[0], web3.eth.accounts[1], 0, 0)
    check_succesful_tx(web3, txhash)
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    ctrlAddrAcct0 = log_entries[0]['args']['controller']
    proxy0 = log_entries[0]['args']['proxy']

    # create 2nd identity
    txhash = idFactory.transact().CreateProxyWithControllerAndRecoveryKey(currencyNetwork.address, web3.eth.accounts[1], web3.eth.accounts[0], 0, 0)
    check_succesful_tx(web3, txhash)
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    ctrlAddrAcct1 = log_entries[0]['args']['controller']
    proxy1 = log_entries[0]['args']['proxy']

    print(ctrlAddrAcct0, "-p", proxy0)
    print(ctrlAddrAcct1, "-p", proxy1)

    trustlineProxy = chain.provider.get_contract_factory("CurrencyNetwork")
    trustlines_contract(trustlineProxy, ctrlAddrAcct0, ctrlAddrAcct1, proxy0, proxy1, web3)

if __name__ == "__main__":
    main()
