

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
