import pytest
from ethereum import tester
import sign
from populus.utils.wait import wait_for_transaction_receipt
from web3.utils.compat import (
    Timeout,
)

trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, tlAB, tlBA)


def deploy(contract_name, chain, *args):
    contract = chain.provider.get_contract_factory(contract_name)
    txhash = contract.deploy(args=args)
    contract_address = chain.wait.for_contract_address(txhash)
    print(contract_name, "contract address is", contract_address)
    return contract(contract_address)


@pytest.fixture()
def trustlines_contract(chain, web3):

    print("Web3 provider is", web3.currentProvider)
    registry = deploy("Registry", chain)
    currencyNetworkFactory = deploy("CurrencyNetworkFactory", chain, registry.address)
    transfer_filter = currencyNetworkFactory.on("CurrencyNetworkCreated")
    txid = currencyNetworkFactory.transact({"from": web3.eth.accounts[0]}).CreateCurrencyNetwork('Trustlines', 'T', web3.eth.accounts[0], 1000, 100, 25, 100);
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    addr_trustlines = log_entries[0]['args']['_currencyNetworkContract']
    print("REAL CurrencyNetwork contract address is", addr_trustlines)

    resolver = deploy("Resolver", chain, addr_trustlines)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getAccountExt(address,address)", "getAccountExtLen()", addr_trustlines);
    transfer_filter = resolver.on("FallbackChanged")
    proxy = deploy("EtherRouter", chain, resolver.address)
    proxied_trustlines = chain.provider.get_contract_factory("CurrencyNetwork")(proxy.address)
    txid = proxied_trustlines.transact({"from": web3.eth.accounts[0]}).setAccount(web3.eth.accounts[7], web3.eth.accounts[8], 2000000, 1, 1, 1, 1, 1, 1, 1);
    print(proxied_trustlines.call().getAccountExt(web3.eth.accounts[7], web3.eth.accounts[8]))

    storagev2 = deploy("CurrencyNetwork", chain)
    txid = resolver.transact({"from": web3.eth.accounts[0]}).setFallback(storagev2.address);
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getUsers()", "getUsersReturnSize()", storagev2.address);
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getFriends(address)", "getFriendsReturnSize(address)", storagev2.address);
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("trustline(address,address)", "trustlineLen(address,address)", storagev2.address);
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("getAccountExt(address,address)", "getAccountExtLen()", storagev2.address);
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("name()", "nameLen()", storagev2.address);
    txid = resolver.transact({"from": web3.eth.accounts[0]}).registerLengthFunction("symbol()", "symbolLen()", storagev2.address);
    wait(transfer_filter)
    log_entries = transfer_filter.get()
    print("Forwarded to ", log_entries[0]['args']['newFallback'])
    txid = proxied_trustlines.transact({"from": web3.eth.accounts[0]}).init('Trustlines', 'T', 1000, 100, 25, 100);

    print(proxied_trustlines.call().getAccountExt(web3.eth.accounts[7], web3.eth.accounts[8]))

    trustlines_contract = proxied_trustlines
    for (A, B, tlAB, tlBA) in trustlines:
        print((A, B, tlAB, tlBA))
        trustlines_contract.transact({"from":web3.eth.accounts[A]}).updateCreditline(web3.eth.accounts[B], tlAB)
        trustlines_contract.transact({"from":web3.eth.accounts[B]}).acceptCreditline(web3.eth.accounts[A], tlAB)
        trustlines_contract.transact({"from":web3.eth.accounts[B]}).updateCreditline(web3.eth.accounts[A], tlBA)
        trustlines_contract.transact({"from":web3.eth.accounts[A]}).acceptCreditline(web3.eth.accounts[B], tlBA)
    return trustlines_contract


@pytest.fixture
def accounts(web3):
    def get(num):
        return [web3.eth.accounts[i] for i in range(num)]
    return get


def print_gas_used(web3, trxid, message):
    receipt = wait_for_transaction_receipt(web3, trxid)
    print(message, receipt["gasUsed"] - 21000)


def wait(transfer_filter):
    with Timeout(30) as timeout:
        while not transfer_filter.get(False):
            timeout.sleep(2)


def test_getaccount(trustlines_contract, accounts):
    (A, B) = accounts(2)
    print(trustlines_contract.call().getAccountExt(A, B))


def test_update_no_accept_creditline_(trustlines_contract, accounts):
    (A, B) = accounts(2)
    trustlines_contract.transact({"from":B}).prepare(A, 100, [A])
    trustlines_contract.transact({"from":B}).transfer(A, 20)
    balAB = trustlines_contract.call().getBalance(A, B)
    trustlines_contract.transact({"from": A}).updateCreditline(B, 150)
    assert 100 == trustlines_contract.call().getCreditline(A, B)
    trustlines_contract.transact({"from": B}).acceptCreditline(A, 150)
    assert 150 == trustlines_contract.call().getCreditline(A, B)
    trustlines_contract.transact({"from": A}).updateCreditline(B, 5)
    assert 5 == trustlines_contract.call().getCreditline(A, B)


def test_reduceCreditline_evenif_above_balance(trustlines_contract, accounts):
    (A, B) = accounts(2)
    trustlines_contract.transact({"from":B}).prepare(A, 100, [A])
    trustlines_contract.transact({"from":B}).transfer(A, 20)
    balAB  = trustlines_contract.call().getBalance(A, B)
    print(balAB)
    trustlines_contract.transact({"from": A}).updateCreditline(B, 10)
    assert 10 == trustlines_contract.call().getCreditline(A, B)

def test_updateAndAcceptCreditline(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    with pytest.raises(tester.TransactionFailed):  # next should fail, no creditline to self
        trustlines_contract.transact({"from": A}).updateCreditline(A, 100)
    trustlines_contract.transact({"from": A}).updateCreditline(B, 100)
    with pytest.raises(tester.TransactionFailed):  # next should fail, sender not allowed to accept
        trustlines_contract.transact({"from": A}).acceptCreditline(A, 100)
    trustlines_contract.transact({"from": B}).acceptCreditline(A, 100)
    trustlines_contract.transact({"from": A}).updateCreditline(B, 100)
    with pytest.raises(tester.TransactionFailed):  # next should fail, sender not allowed to accept
        trustlines_contract.transact({"from": C}).acceptCreditline(A, 100)


def test_cashCheque(trustlines_contract, accounts, web3):
    (A, B) = accounts(2)
    balA = trustlines_contract.call().balanceOf(A)
    balB = trustlines_contract.call().balanceOf(B)
    mtime = trustlines_contract.call().calculateMtime()
    data = trustlines_contract.call().shaOfValue(A, B, 90, mtime + 1)
    sig, addr = sign.check(bytes(data, "raw_unicode_escape"), tester.k0)
    assert addr == A
    trustlines_contract.transact({"from": A}).prepareFrom(A, B, 100, [B])
    assert(trustlines_contract.transact({"from": A}).cashCheque(A, B, 90, mtime + 1, sig))
    assert trustlines_contract.call().balanceOf(A) == balA - 90
    assert trustlines_contract.call().balanceOf(B) == balB + 90

def test_preparePath(trustlines_contract, accounts):
    (A, B, C, D, E) = accounts(5)
    print (trustlines_contract.call().getCreditline(A, B))
    print (trustlines_contract.call().spendableTo(A, B))
    assert trustlines_contract.call().balanceOf(A) == 700
    trustlines_contract.transact({"from":A}).prepare(C, 100, [E, D, C])
    trustlines_contract.transact({"from":A}).transfer(C, 20)
    assert trustlines_contract.call().balanceOf(A) == 680
    trustlines_contract.transact({"from":A}).prepare(C, 100, [E, D, C])
#    with pytest.raises(tester.TransactionFailed):
    trustlines_contract.transact({"from":A}).transfer(C, 30)
    assert trustlines_contract.call().balanceOf(A) == 651
    trustlines_contract.transact({"from":A}).transfer(C, 20)
    assert trustlines_contract.call().balanceOf(A) == 631

def test_prepareFrom(web3, trustlines_contract, accounts):
    (A, B, C, D, E) = accounts(5)
    assert trustlines_contract.call().balanceOf(B) == 350
    trxid = trustlines_contract.transact({"from":A}).prepareFrom(B, C, 100, [C])
    print_gas_used(web3, trxid, 'hop')
    assert trustlines_contract.call().balanceOf(B) == 350
    trxid = trustlines_contract.transact({"from":A}).transferFrom(B, C, 20)
    print_gas_used(web3, trxid, 'hop')
    assert trustlines_contract.call().balanceOf(B) == 330
    trustlines_contract.transact({"from":A}).prepareFrom(B, C, 100, [C])
#    with pytest.raises(tester.TransactionFailed):
    trustlines_contract.transact({"from":A}).transferFrom(B, C, 30)
    assert trustlines_contract.call().balanceOf(B) == 300


def test_approveUpdateAccept(trustlines_contract, accounts):
    (A, B) = accounts(2)
    trustlines_contract.transact({"from":A}).updateCreditline(B, 150)
    trustlines_contract.transact({"from":B}).acceptCreditline(A, 150)


def test_trustlines(trustlines_contract, web3):
    for (A, B, tlAB, tlBA) in trustlines:
        assert trustlines_contract.call().trustline(web3.eth.accounts[A], web3.eth.accounts[B]) == [tlAB, tlBA, 0]

def test_spendable(trustlines_contract, accounts):
    (A, B) = accounts(2)
    assert trustlines_contract.call().spendableTo(A, B) == 150
    assert trustlines_contract.call().spendableTo(B, A) == 100
    trustlines_contract.transact({"from":A}).prepare(B, 100, [B])
    trustlines_contract.transact({"from":A}).transfer(B, 40)
    assert trustlines_contract.call().spendableTo(A, B) == 110
    assert trustlines_contract.call().spendableTo(B, A) == 140


def test_balance_of(trustlines_contract, accounts, web3):
    (A, B, C, D, E) = accounts(5)
    assert trustlines_contract.call().balanceOf(A) == 700
    trustlines_contract.transact({"from":A}).transfer(B, 40, 100, [B])
    assert trustlines_contract.call().balanceOf(A) == 660
    trxid = trustlines_contract.transact({"from":A}).transfer(C, 20, 100, [E, D, C])
    print_gas_used(web3, trxid, 'hop')
    trxid = trustlines_contract.transact({"from":A}).transfer(C, 20, 100, [B, C])
    print_gas_used(web3, trxid, 'hop')
    assert trustlines_contract.call().balanceOf(A) == 620
    trustlines_contract.transact({"from":E}).transfer(A, 70, 100, [A])
    assert trustlines_contract.call().balanceOf(A) == 690
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from":A}).transfer(B, 1000, 100, [B])
    assert trustlines_contract.call().balanceOf(A) == 690


def test_total_supply(trustlines_contract):
    assert trustlines_contract.call().totalSupply() == 3250


def test_total_supply_after_credits(trustlines_contract, accounts):
    (A, B) = accounts(2)
    trustlines_contract.transact({"from":A}).updateCreditline(B, 150)
    trustlines_contract.transact({"from":B}).acceptCreditline(A, 150)
    assert trustlines_contract.call().totalSupply() == 3300
    trustlines_contract.transact({"from":A}).updateCreditline(B, 0)
    assert trustlines_contract.call().totalSupply() == 3150
    trustlines_contract.transact({"from":B}).updateCreditline(A, 0)
    assert trustlines_contract.call().totalSupply() == 3000

def test_transactions(trustlines_contract, accounts):
    (A, B) = accounts(2)
    assert trustlines_contract.call().trustline(A, B) == [100, 150, 0]
    trustlines_contract.transact({"from":A}).transfer(B, 10, 100, [B])
    res = trustlines_contract.transact({"from":A}).transfer(B, 10, 100, [B])
    assert res
    assert trustlines_contract.call().trustline(A, B) == [100, 150, -20]
    assert trustlines_contract.call().trustline(B, A) == [150, 100, 20]
    trustlines_contract.transact({"from":B}).transfer(A, 20, 100, [A])


def test_mediated_transfer_array(trustlines_contract, accounts, web3):
    (A, B, C, D, E) = accounts(5)

    # 0 hops (using mediated)
    assert trustlines_contract.call().trustline(A, B)[2] == 0
    path = [B]
    trustlines_contract.transact({"from": A}).prepare(B, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(B, 21)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -21

    # 1 hops (using mediated)
    path = [B,C]
    trustlines_contract.transact({"from": A}).prepare(C, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(C, 21)
    print_gas_used(web3, res, '1 hop')
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -42
    assert trustlines_contract.call().trustline(B, C)[2] == -21

    # 2 hops (using mediated)
    path = [B, C, D]
    trustlines_contract.transact({"from": A}).prepare(D, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(D, 21)
    print_gas_used(web3, res, '2 hops')
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -63
    assert trustlines_contract.call().trustline(B, C)[2] == -42

    # 2 hops (using mediated)
    path = [B, C, D, E]
    trustlines_contract.transact({"from": A}).prepare(E, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(E, 21)
    print_gas_used(web3, res, '2 hops')
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -84
    assert trustlines_contract.call().trustline(D, E)[2] == -21

    # 0 hops (using mediated) payback
    path = [A]
    trustlines_contract.transact({"from": B}).prepare(A, 100, path)
    res = trustlines_contract.transact({"from":B}).transfer(A, 84)
    print_gas_used(web3, res, '0 hops')
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == 0
    assert trustlines_contract.call().trustline(D, E)[2] == -21


def test_mediated_transfer(trustlines_contract, accounts, web3):
    (A, B, C, D, E) = accounts(5)

    # 0 hops (using mediated)
    assert trustlines_contract.call().trustline(A, B) & (2**63-1) == 0
    path = [B]
    trustlines_contract.transact({"from": A}).prepare(B, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(B, 21)
    assert res
    assert ((trustlines_contract.call().trustline(A, B) & (2**63-1) == 21) and (trustlines_contract.call().trustline(A, B) & (2**63) == (2**63)))

    # 1 hops (using mediated)
    path = [B,C]
    trustlines_contract.transact({"from": A}).prepare(C, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(C, 21)
    print_gas_used(web3, res, '1 hop')
    assert res
    assert ((trustlines_contract.call().trustline(A, B) & (2**63-1) == 42) and (trustlines_contract.call().trustline(A, B) & (2**63) == (2**63)))
    assert ((trustlines_contract.call().trustline(B, C) & (2**63-1) == 21) and (trustlines_contract.call().trustline(B, C) & (2**63) == (2**63)))

    # 2 hops (using mediated)
    path = [B, C, D]
    trustlines_contract.transact({"from": A}).prepare(D, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(D, 21)
    print_gas_used(web3, res, '2 hops')
    assert res
    assert ((trustlines_contract.call().trustline(A, B) & (2**63-1) == 63) and (trustlines_contract.call().trustline(A, B) & (2**63) == (2**63)))
    assert ((trustlines_contract.call().trustline(B, C) & (2**63-1) == 42) and (trustlines_contract.call().trustline(B, C) & (2**63) == (2**63)))

    # 2 hops (using mediated)
    path = [B, C, D, E]
    trustlines_contract.transact({"from": A}).prepare(E, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(E, 21)
    print_gas_used(web3, res, '2 hops')
    assert res
    assert ((trustlines_contract.call().trustline(A, B) & (2**63-1) == 84) and (trustlines_contract.call().trustline(A, B) & (2**63) == (2**63)))
    assert ((trustlines_contract.call().trustline(D, E) & (2**63-1) == 21) and (trustlines_contract.call().trustline(D, E) & (2**63) == (2**63)))

    # 0 hops (using mediated) payback
    path = [A]
    trustlines_contract.transact({"from": B}).prepare(A, 100, path)
    res = trustlines_contract.transact({"from":B}).transfer(A, 84)
    print_gas_used(web3, res, '0 hops')
    assert res
    assert ((trustlines_contract.call().trustline(A, B) & (2**63-1) == 0) and (trustlines_contract.call().trustline(A, B) & (2**63) == (2**63)))
    assert ((trustlines_contract.call().trustline(D, E) & (2**63-1) == 21) and (trustlines_contract.call().trustline(D, E) & (2**63) == (2**63)))


def test_mediated_transfer_not_enough_balance(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    path = [B, C]
    trustlines_contract.transact({"from": A}).prepare(C, 100, path)
    res = trustlines_contract.transact({"from":A}).transfer(C, 150)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -150  # 150 were spend
    with pytest.raises(tester.TransactionFailed): # next should fail
        trustlines_contract.transact({"from":A}).prepare(C, 100, path)
        trustlines_contract.transact({"from":A}).transfer(C, 1)
    assert trustlines_contract.call().trustline(A, B)[2] == -150  # should be unchanged


def test_mediated_transfer_no_path(trustlines_contract, accounts):
    (A, B, C, D) = accounts(4)
    path = [C, D]
    with pytest.raises(tester.TransactionFailed):  # next should fail because gap in path
        trustlines_contract.transact({"from": A}).prepare(D, 100, path)
        trustlines_contract.transact({"from": A}).transfer(D, 1)
    assert trustlines_contract.call().trustline(A, B)[2] == 0  # should be unchanged
    path = [B, D]
    with pytest.raises(tester.TransactionFailed):  # next should fail because gap in path
        trustlines_contract.transact({"from": A}).prepare(D, 100, path)
        trustlines_contract.transact({"from": A}).transfer(D, 1)
    path = []
    with pytest.raises(tester.TransactionFailed):  # next should fail because empty path
        trustlines_contract.transact({"from": A}).prepare(D, 100, path)
        trustlines_contract.transact({"from": A}).transfer(D, 1)


def test_mediated_transfer_target_doesnt_match(trustlines_contract, accounts):
    (A, B, C, D) = accounts(4)
    path = [B, C]
    with pytest.raises(tester.TransactionFailed):  # next should fail because target does not match
        trustlines_contract.transact({"from": A}).prepare(D, 100, path)
        trustlines_contract.transact({"from": A}).transfer(D, 1)


def test_defaults(trustlines_contract, accounts):
    (A, _, C) = accounts(3)
    assert trustlines_contract.call().trustline(A, C) == [0, 0, 0]  # should default to 0


def test_trustlines_lt0(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    with pytest.raises(TypeError):
        trustlines_contract.transact({"from":A}).updateCreditline(B, -1)
        trustlines_contract.transact({"from":B}).acceptCreditline(A, -1)


def test_trustlines_lt_balance(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    path = [B, C]
    print(trustlines_contract.call().trustline(B, C))
    print(trustlines_contract.call().trustline(C, B))
    print("balanceC", trustlines_contract.call().balanceOf(C));
    trustlines_contract.transact({"from": A}).prepare(C, 100, path)
    trustlines_contract.transact({"from": A}).transfer(C, 150)
    trustlines_contract.transact({"from": B}).updateCreditline(A, 100) # should fail, because below balance
    assert trustlines_contract.call().trustline(B, A) == [100, 100, 150]
    path = [B, A]
    print(trustlines_contract.call().trustline(B, C))
    print(trustlines_contract.call().trustline(C, B))
    print("balanceC", trustlines_contract.call().balanceOf(C));
    trustlines_contract.transact({"from": C}).prepare(A, 100, path)
    trustlines_contract.transact({"from": C}).transfer(A, 50)
    trustlines_contract.transact({"from": B}).updateCreditline(A, 102)  # should now work

    print(trustlines_contract.call().trustline(B, A))
    print("balanceC", trustlines_contract.call().balanceOf(C));


    res = trustlines_contract.transact({"from": A}).acceptCreditline(B, 102)  # should now work
    assert res
    assert trustlines_contract.call().trustline(B, A) == [100, 100, 100]


def test_meta(trustlines_contract):
    assert trustlines_contract.call().name().replace('\x00', '') == "Trustlines"
    assert trustlines_contract.call().symbol().replace('\x00', '') == "T"


def test_users(trustlines_contract, accounts):
    (A, B, C, D, E) = accounts(5)
    assert trustlines_contract.call().getUsers() == list(map(lambda item: item,[A, B, C, D, E]))
    assert trustlines_contract.call().getFriends(A) == list(map(lambda item: item,[B, E]))


def test_same_user(trustlines_contract, accounts):
    (A, B) = accounts(2)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).updateCreditline(A, 100)  # can not create trustline with himself
        trustlines_contract.transact({"from": A}).acceptCreditline(A, 100)  # can not create trustline with himself
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.call().trustline(B, B)  # can not get trustline with himself


def test_same_user_transfer(trustlines_contract, accounts):
    (_, B, _, D) = accounts(4)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": B}).transfer(B, 10)  # can not get directly transfer with himself
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": D}).prepare(D, 100, [D])
        trustlines_contract.transact({"from": D}).transfer(D, 100)  # can not get directly transfer with himself


def test_too_high_value_credit(trustlines_contract, accounts):
    (A, B) = accounts(2)
    #  but the following should work
    trustlines_contract.transact({"from": A}).updateCreditline(B, 2**32-1)
    trustlines_contract.transact({"from": B}).acceptCreditline(A, 2**32-1)
    trustlines_contract.transact({"from": B}).updateCreditline(A, 2**32-1)
    trustlines_contract.transact({"from": A}).acceptCreditline(B, 2**32-1)
    assert trustlines_contract.call().trustline(A, B) == [2 ** 32 - 1, 2 ** 32 - 1, 0]


def test_too_high_value_transfer(trustlines_contract, accounts):
    (A, B) = accounts(2)
#    with pytest.raises(tester.TransactionFailed):
#        trustlines_contract.transact({"from": A}).transfer(B, 2**32 + 1, 10000, [B])
#    with pytest.raises(tester.TransactionFailed):
#        trustlines_contract.transact({"from": A}).transfer(B, 2**33 + 1, 10000, [B])
    #  but the following should work
    trustlines_contract.transact({"from": A}).updateCreditline(B, 2**16 - 1)
    trustlines_contract.transact({"from": B}).acceptCreditline(A, 2**16 - 1)
    trustlines_contract.transact({"from": B}).updateCreditline(A, 0)
#    trustlines_contract.transact({"from": A}).acceptCreditline(B, 0)
    trustlines_contract.transact({"from": B}).transfer(A, 2**16 - 1, 50000, [A])
    assert trustlines_contract.call().trustline(A, B) == [2**16 - 1, 0, 2**16 - 1]


def test_too_high_value_mediatedTransfer(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    #  but the following should work
    trustlines_contract.transact({"from": A}).updateCreditline(B, 2**32 - 1)
    trustlines_contract.transact({"from": B}).acceptCreditline(A, 2**32 - 1)
    trustlines_contract.transact({"from": B}).updateCreditline(C, 2**32 - 1)
    trustlines_contract.transact({"from": C}).acceptCreditline(B, 2**32 - 1)
    trustlines_contract.transact({"from": C}).updateCreditline(B, 0)
#    trustlines_contract.transact({"from": B}).acceptCreditline(C, 0)
    trustlines_contract.transact({"from": C}).prepare(A, 50000, [B, A])
    trustlines_contract.transact({"from": C}).transfer(A, 2**16-1)
    assert trustlines_contract.call().trustline(C, B) == [0, 2**32 - 1, -(2**16 - 1)]


def test_negative_value_transfer_credit(trustlines_contract, accounts):
    (A, B) = accounts(2)
    with pytest.raises(TypeError):
        trustlines_contract.transact({"from": A}).transfer(B, -10)
    with pytest.raises(TypeError):
        trustlines_contract.transact({"from": A}).updateCreditline(B, -10)
