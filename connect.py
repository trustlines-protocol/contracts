import json, time, re;
from web3 import Web3, HTTPProvider

trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, tlAB, tlBA)

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

def trustlines_contract(trustlines_contract, web3):
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
    with open('./build/contracts/CurrencyNetwork.json') as data_file:
        data = data_file.read()
    addr = re.search(r'"address": "(.+)",', data, re.M|re.I).group(1)
    data = re.search(r'"abi": (.+),.*"unlinked_binary"', data, re.M|re.I|re.DOTALL).group(1)
    return addr, json.loads(data)

def main():
    web3 = Web3(HTTPProvider('http://localhost:8545'))
    (addr, jabi) = abi()
    print("\ncalling contract at address {}\n".format(addr))
    ctri = web3.eth.contract(abi=jabi, address=addr)
    assert(ctri.call().spendable(addr) == 0)
    # start integration tests
    trustlines_contract(ctri, web3)
    test_trustlines(ctri, web3)

if __name__ == "__main__":
    main()