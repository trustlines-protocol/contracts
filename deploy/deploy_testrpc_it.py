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


def test_trustlines(trustlines_contract, web3):
    for (A, B, tlAB, tlBA) in trustlines:
        assert trustlines_contract.call().trustline(web3.eth.accounts[A], web3.eth.accounts[B]) == [tlAB, tlBA, 0]


def check_successful_tx(msg: str, web3: Web3, txid: str, timeout=180) -> dict:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt
    """
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    txinfo = web3.eth.getTransaction(txid)
    assert txinfo["gas"] != receipt["gasUsed"]
    print(msg, " gas used: ", receipt["gasUsed"] - 21000)
    return receipt


def prepare_trustlines_contract(trustlines_contract, web3):
    for (A, B, tlAB, tlBA) in trustlines:
        print((A, B, tlAB, tlBA))
        txid = trustlines_contract.transact({"from":web3.eth.accounts[A]}).updateCreditline(web3.eth.accounts[B], tlAB)
        check_successful_tx("uCL", web3, txid)
        txid = trustlines_contract.transact({"from":web3.eth.accounts[B]}).acceptCreditline(web3.eth.accounts[A], tlAB)
        check_successful_tx("aCL", web3, txid)
        txid = trustlines_contract.transact({"from":web3.eth.accounts[B]}).updateCreditline(web3.eth.accounts[A], tlBA)
        check_successful_tx("uCL", web3, txid)
        txid = trustlines_contract.transact({"from":web3.eth.accounts[A]}).acceptCreditline(web3.eth.accounts[B], tlBA)
        check_successful_tx("aCL", web3, txid)
    return trustlines_contract


def wait(transfer_filter):
    with Timeout(30) as timeout:
        while not transfer_filter.get(False):
            timeout.sleep(2)


def deploy(contract_name, chain, *args):
    contract = chain.provider.get_contract_factory(contract_name)
    txhash = contract.deploy(args=args)
    receipt = check_successful_tx("deploy ", chain.web3, txhash)
    id_address = receipt["contractAddress"]
    print(contract_name, "contract address is", id_address)
    return contract(id_address)


def accounts(web3, num):
    return [web3.eth.accounts[i] for i in range(num)]


def test_mediated_transfer_array(trustlines_contract, web3):
    (A, B, C, D, E) = accounts(web3, 5)

    # 0 hops (using mediated)
    assert trustlines_contract.call().trustline(A, B)[2] == 0
    path = [B]
    res = trustlines_contract.transact({"from": A}).prepare(B, 100, path)
    check_successful_tx("prepare", web3, res)
    res = trustlines_contract.transact({"from":A}).transfer(B, 21)
    check_successful_tx("0 hops", web3, res)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -21

    # 1 hops (using mediated)
    path = [B,C]
    res = trustlines_contract.transact({"from": A}).prepare(C, 100, path)
    check_successful_tx("prepare", web3, res)
    res = trustlines_contract.transact({"from":A}).transfer(C, 21)
    check_successful_tx("1 hop", web3, res)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -42
    assert trustlines_contract.call().trustline(B, C)[2] == -21

    # 2 hops (using mediated)
    path = [B, C, D]
    res = trustlines_contract.transact({"from": A}).prepare(D, 100, path)
    check_successful_tx("prepare", web3, res)
    res = trustlines_contract.transact({"from":A}).transfer(D, 21)
    check_successful_tx("2 hops", web3, res)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -63
    assert trustlines_contract.call().trustline(B, C)[2] == -42

    # 3 hops (using mediated)
    path = [B, C, D, E]
    res = trustlines_contract.transact({"from": A}).prepare(E, 100, path)
    check_successful_tx("prepare", web3, res)
    res = trustlines_contract.transact({"from":A}).transfer(E, 21)
    check_successful_tx("3 hops", web3, res)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -84
    assert trustlines_contract.call().trustline(D, E)[2] == -21

    # 0 hops (using mediated) payback
    path = [A]
    res = trustlines_contract.transact({"from": B}).prepare(A, 100, path)
    check_successful_tx("prepare", web3, res)
    res = trustlines_contract.transact({"from":B}).transfer(A, 84)
    check_successful_tx("0 hops", web3, res)
    assert res
    # still wrong calculations TODO
    assert trustlines_contract.call().trustline(A, B)[2] == -10
    assert trustlines_contract.call().trustline(D, E)[2] == -21


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
    receipt = check_successful_tx("create", web3, txid)
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    addr_trustlines = log_entries[0]['args']['_currencyNetworkContract']
    print("REAL CurrencyNetwork contract address is", addr_trustlines)

    resolver = deploy("Resolver", chain, addr_trustlines)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getAccountExt(address,address)", "getAccountExtLen()", addr_trustlines);
    receipt = check_successful_tx("resolver", web3, txid)
    transfer_filter = resolver.on("FallbackChanged")
    proxy = deploy("EtherRouter", chain, resolver.address)
    proxied_trustlines = chain.provider.get_contract_factory("CurrencyNetwork")(proxy.address)
    txid = proxied_trustlines.transact({"from": web3.eth.accounts[0]}).setAccount(web3.eth.accounts[6], web3.eth.accounts[7], 2000000, 1, 1, 1, 1, 1, 1, 1);
    receipt = check_successful_tx("setAccount", web3, txid)
    print(proxied_trustlines.call().getAccountExt(web3.eth.accounts[6], web3.eth.accounts[7]))

    storagev2 = deploy("CurrencyNetwork", chain)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).setFallback(storagev2.address);
    receipt = check_successful_tx("setFallback", web3, txid)
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    print("Forwarded to ", log_entries[0]['args']['newFallback'])
    txid = proxied_trustlines.transact({"from": web3.eth.accounts[0]}).init('Trustlines', 'T', 1000, 100, 25, 100)
    receipt = check_successful_tx("init", web3, txid)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getAccountExt(address,address)", "getAccountExtLen()", storagev2.address);
    receipt = check_successful_tx("register", web3, txid)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("trustline(address,address)", "trustlineLen(address,address)", storagev2.address);
    receipt = check_successful_tx("register", web3, txid)
    print(proxied_trustlines.call().getAccountExt(web3.eth.accounts[6], web3.eth.accounts[7]))

    prepare_trustlines_contract(proxied_trustlines, web3)
    test_trustlines(proxied_trustlines, web3)
    test_mediated_transfer_array(proxied_trustlines, web3)


if __name__ == "__main__":
    main()
