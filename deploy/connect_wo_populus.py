import json, time, sys, os
from web3 import Web3, HTTPProvider

trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, tlAB, tlBA)


contract_abi_path = ''


def check_successful_tx(web3: Web3, txid: str, timeout=120) -> dict:
    for i in range(0, timeout):
        txn_receipt = web3.eth.getTransactionReceipt(txid)
        if txn_receipt is not None and txn_receipt['blockHash'] is not None:
            break
        time.sleep(1)
    if txn_receipt is None or txn_receipt['blockHash'] is None:
        raise RuntimeError('Transaction not found.')
    txn = web3.eth.getTransaction(txid)
    # Solidity did not throw (otherwise gas and gasUsed would be different)
    assert txn["gas"] != txn_receipt["gasUsed"]
    return txn

def prepare_trustlines_contract(trustlines_contract, web3):
    for (A, B, tlAB, tlBA) in trustlines:
        print((A, B, tlAB, tlBA))
        txid = trustlines_contract.transact({"from":web3.eth.accounts[A]}).updateCreditline(web3.eth.accounts[B], tlAB)
        check_successful_tx(web3, txid)
        txid = trustlines_contract.transact({"from":web3.eth.accounts[B]}).acceptCreditline(web3.eth.accounts[A], tlAB)
        check_successful_tx(web3, txid)
        txid = trustlines_contract.transact({"from":web3.eth.accounts[B]}).updateCreditline(web3.eth.accounts[A], tlBA)
        check_successful_tx(web3, txid)
        txid = trustlines_contract.transact({"from":web3.eth.accounts[A]}).acceptCreditline(web3.eth.accounts[B], tlBA)
        check_successful_tx(web3, txid)
    return trustlines_contract

def accounts(web3):
    def get(num):
        return [web3.eth.accounts[i] for i in range(num)]
    return get

def test_trustlines(trustlines_contract, web3):
    for (A, B, tlAB, tlBA) in trustlines:
        assert trustlines_contract.call().trustline(web3.eth.accounts[A], web3.eth.accounts[B]) == [tlAB, tlBA, 0]

def abi():
    global contract_abi_path
    if not contract_abi_path:
        contract_abi_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'build/contracts.json')
    with open(contract_abi_path) as abi_file:
        contract_abis = json.load(abi_file)
        trustlines_abi  = contract_abis['CurrencyNetwork']['abi']
    return trustlines_abi


def main():
    web3 = Web3(HTTPProvider('http://localhost:8545'))
    addr = sys.argv[1]
    print("\ncalling trustlines contract at address {}\n".format(addr))
    trustlines_contract = web3.eth.contract(abi=abi(), address=addr)
    prepare_trustlines_contract(trustlines_contract, web3)
    test_trustlines(trustlines_contract, web3)

if __name__ == "__main__":
    main()