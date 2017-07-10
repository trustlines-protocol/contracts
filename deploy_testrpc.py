"""Deploy Edgeless token and smart contract in testnet.
A simple Python script to deploy contracts and then do a smoke test for them.
"""
from populus import Project
from populus.utils.wait import wait_for_transaction_receipt
from web3 import Web3
from web3.utils.compat import (
    Timeout,
)

def check_succesful_tx(web3: Web3, txid: str, timeout=180) -> dict:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt
    """
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    txinfo = web3.eth.getTransaction(txid)
    assert txinfo["gas"] != receipt["gasUsed"]
    return receipt

def main():
    project = Project()
    chain_name = "testrpclocal"
    print("Make sure {} chain is running, you can connect to it, or you'll get timeout".format(chain_name))

    with project.get_chain(chain_name) as chain:
        web3 = chain.web3
        print("Web3 provider is", web3.currentProvider)

        identity_factory = chain.provider.get_contract_factory("CurrencyNetwork")
        txhash = identity_factory.deploy(transaction={"gas": 4000000}, args=["Trustline", "T"])
        receipt = check_succesful_tx(chain.web3, txhash)
        id_address = receipt["contractAddress"]
        print(identity_factory, " contract address is", id_address)

if __name__ == "__main__":
    main()
