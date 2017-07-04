import pytest
from ethereum import tester

trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, tlAB, tlBA)

@pytest.fixture()
def trustlines_contract(chain):
    Trustlines = chain.provider.get_contract_factory('CurrencyNetwork')
    deploy_txn_hash = Trustlines.deploy(args=[
        "Testcoin", "T"
    ])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    trustlines_contract = Trustlines(address=contract_address)
    for (A, B, tlAB, tlBA) in trustlines:
        trustlines_contract.transact({"from":chain.web3.eth.accounts[A]}).updateCreditline(chain.web3.eth.accounts[B], tlAB)
        trustlines_contract.transact({"from":chain.web3.eth.accounts[B]}).updateCreditline(chain.web3.eth.accounts[A], tlBA)
    return trustlines_contract

@pytest.fixture
def accounts(web3):
    def get(num):
        return [web3.eth.accounts[i] for i in range(num)]
    return get


def test_trustlines(trustlines_contract, web3):
    for (A, B, tlAB, tlBA) in trustlines:
        assert trustlines_contract.call().trustline(web3.eth.accounts[A], web3.eth.accounts[B]) == [tlAB, tlBA, 0]

def test_spendable(trustlines_contract, accounts):
    (A, B) = accounts(2)
    assert trustlines_contract.call().spendableTo(A, B) == 150
    assert trustlines_contract.call().spendableTo(B, A) == 100
    trustlines_contract.transact({"from":A}).transfer(B, 40)
    assert trustlines_contract.call().spendableTo(A, B) == 110
    assert trustlines_contract.call().spendableTo(B, A) == 140

def test_balance_of(trustlines_contract, web3, accounts):
    (A, B, C, D, E) = accounts(5)
    assert trustlines_contract.call().balanceOf(A) == 700
    trustlines_contract.transact({"from":A}).transfer(B, 40)
    assert trustlines_contract.call().balanceOf(A) == 660
    trustlines_contract.transact({"from":A}).mediatedTransfer(C, 20, [E, D, C])
    assert trustlines_contract.call().balanceOf(A) == 640
    trustlines_contract.transact({"from":E}).transfer(A, 70)
    assert trustlines_contract.call().balanceOf(A) == 710
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from":A}).transfer(B, 1000)
    assert trustlines_contract.call().balanceOf(A) == 710

def test_total_supply(trustlines_contract):
    assert trustlines_contract.call().totalSupply() == 3250

def test_total_supply_after_credits(trustlines_contract, accounts):
    (A, B) = accounts(2)
    trustlines_contract.transact({"from":A}).updateCreditline(B, 150)
    assert trustlines_contract.call().totalSupply() == 3300
    trustlines_contract.transact({"from":A}).updateCreditline(B, 0)
    assert trustlines_contract.call().totalSupply() == 3150
    trustlines_contract.transact({"from":B}).updateCreditline(A, 0)
    assert trustlines_contract.call().totalSupply() == 3000

def test_transactions(trustlines_contract, accounts):
    (A, B) = accounts(2)
    assert trustlines_contract.call().trustline(A, B) == [100, 150, 0]
    trustlines_contract.transact({"from":A}).transfer(B, 10)
    res = trustlines_contract.transact({"from":A}).transfer(B, 10)
    assert res
    assert trustlines_contract.call().trustline(A, B) == [100, 150, -20]
    assert trustlines_contract.call().trustline(B, A) == [150, 100, 20]
    trustlines_contract.transact({"from":B}).transfer(A, 20)

def test_mediated_transfer(trustlines_contract, accounts):
    (A, B, C, D, E) = accounts(5)

    # 0 hops (using mediated)
    assert trustlines_contract.call().trustline(A, B)[2] == 0
    path = [B]
    res = trustlines_contract.transact({"from":A}).mediatedTransfer(B, 21, path)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -21

    # 1 hops (using mediated)
    path = [B,C]
    res = trustlines_contract.transact({"from":A}).mediatedTransfer(C, 21, path)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -42 # spend 2 times
    assert trustlines_contract.call().trustline(B, C)[2] == -21 # received 21

    # 2 hops (using mediated)
    path = [B, C, D]
    res = trustlines_contract.transact({"from":A}).mediatedTransfer(D, 21, path)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -63  # spend 3 times
    assert trustlines_contract.call().trustline(B, C)[2] == -42  # relay 2 times

    # 2 hops (using mediated)
    path = [B, C, D, E]
    res = trustlines_contract.transact({"from":A}).mediatedTransfer(E, 21, path)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -84  # spend 4 times
    assert trustlines_contract.call().trustline(D, E)[2] == -21  # received 21

    # 0 hops (using mediated) payback
    path = [A]
    res = trustlines_contract.transact({"from":B}).mediatedTransfer(A, 84, path)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == 0  # balanced
    assert trustlines_contract.call().trustline(D, E)[2] == -21  # unchanged

def test_mediated_transfer_not_enough_balance(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    path = [B, C]
    res = trustlines_contract.transact({"from":A}).mediatedTransfer(C, 150, path)
    assert res
    assert trustlines_contract.call().trustline(A, B)[2] == -150  # 150 were spend
    with pytest.raises(tester.TransactionFailed): # next should fail
        trustlines_contract.transact({"from":A}).mediatedTransfer(C, 1, path)
    assert trustlines_contract.call().trustline(A, B)[2] == -150  # should be unchanged

def test_mediated_transfer_no_path(trustlines_contract, accounts):
    (A, B, C, D) = accounts(4)
    path = [C, D]
    with pytest.raises(tester.TransactionFailed):  # next should fail because gap in path
        trustlines_contract.transact({"from": A}).mediatedTransfer(D, 1, path)
    assert trustlines_contract.call().trustline(A, B)[2] == 0  # should be unchanged
    path = [B, D]
    with pytest.raises(tester.TransactionFailed):  # next should fail because gap in path
        trustlines_contract.transact({"from": A}).mediatedTransfer(D, 1, path)
    path = []
    with pytest.raises(tester.TransactionFailed):  # next should fail because empty path
        trustlines_contract.transact({"from":A}).mediatedTransfer(D, 1, path)

def test_mediated_transfer_target_doesnt_match(trustlines_contract, accounts):
    (A, B, C, D) = accounts(4)
    path = [B, C]
    with pytest.raises(tester.TransactionFailed):  # next should fail because target does not match
        trustlines_contract.transact({"from":A}).mediatedTransfer(D, 1, path)


def test_defaults(trustlines_contract, accounts):
    (A, _, C) = accounts(3)
    assert trustlines_contract.call().trustline(A, C) == [0, 0, 0]  # should default to 0


def test_trustlines_lt0(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    with pytest.raises(TypeError):
        trustlines_contract.transact({"from":A}).updateCreditline(B, -1)



def test_trustlines_lt_balance(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    path = [B, C]
    trustlines_contract.transact({"from":A}).mediatedTransfer(C, 150, path)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": B}).updateCreditline(A, 100) # should fail, because below balance
    assert trustlines_contract.call().trustline(B, A) == [150, 100, 150]
    path = [B, A]
    trustlines_contract.transact({"from": C}).mediatedTransfer(A, 50, path)
    res = trustlines_contract.transact({"from": B}).updateCreditline(A, 100)  # should now work
    assert res
    assert trustlines_contract.call().trustline(B, A) == [100, 100, 100]


def test_meta(trustlines_contract):
    assert trustlines_contract.call().name()   == "Testcoin"
    assert trustlines_contract.call().symbol() == "T"
    assert trustlines_contract.call().decimals() == 2


def test_users(trustlines_contract, accounts):
    (A, B, C, D, E) = accounts(5)
    assert trustlines_contract.call().users() == list(map(lambda item: item,[A, B, C, D, E]))
    assert trustlines_contract.call().friends(A) == list(map(lambda item: item,[B, E]))


def test_same_user(trustlines_contract, accounts):
    (A, B) = accounts(2)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).updateCreditline(A, 100)  # can not create trustline with himself
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.call().trustline(B, B)  # can not get trustline with himself


def test_same_user_transfer(trustlines_contract, accounts):
    (_, B, _, D) = accounts(4)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": B}).transfer(B, 10)  # can not get directly transfer with himself
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": D}).mediatedTransfer(D, 100, [D])  # can not get directly transfer with himself


def test_too_high_value_credit(trustlines_contract, accounts):
    (A, B) = accounts(2)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).updateCreditline(B, 2**192)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).updateCreditline(B, 2**200)
    #  but the following should work
    trustlines_contract.transact({"from": A}).updateCreditline(B, 2**192 - 1)
    trustlines_contract.transact({"from": B}).updateCreditline(A, 2**192 - 1)
    assert trustlines_contract.call().trustline(A, B) == [2 ** 192 - 1, 2 ** 192 - 1, 0]


def test_too_high_value_transfer(trustlines_contract, accounts):
    (A, B) = accounts(2)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).transfer(B, 2**192 + 1)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).transfer(B, 2**200 + 1)
    #  but the following should work
    trustlines_contract.transact({"from": A}).updateCreditline(B, 2**192 - 1)
    trustlines_contract.transact({"from": B}).updateCreditline(A, 0)
    trustlines_contract.transact({"from": B}).transfer(A, 2**192 - 1)
    assert trustlines_contract.call().trustline(A, B) == [2**192 - 1, 0, 2**192 - 1]


def test_too_high_value_mediatedTransfer(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).mediatedTransfer(C, 2**192, [B, C])
    with pytest.raises(tester.TransactionFailed):
        trustlines_contract.transact({"from": A}).mediatedTransfer(C, 2 ** 200 + 1, [B, C])
    #  but the following should work
    trustlines_contract.transact({"from": A}).updateCreditline(B, 2**192 - 1)
    trustlines_contract.transact({"from": B}).updateCreditline(C, 2**192 - 1)
    trustlines_contract.transact({"from": C}).updateCreditline(B, 0)
    trustlines_contract.transact({"from": C}).mediatedTransfer(A, 2**192 - 1, [B, A])
    assert trustlines_contract.call().trustline(C, B) == [0, 2**192 - 1, -(2**192 - 1)]


def test_negative_value_transfer_credit(trustlines_contract, accounts):
    (A, B) = accounts(2)
    with pytest.raises(TypeError):
        trustlines_contract.transact({"from": A}).transfer(B, -10)
    with pytest.raises(TypeError):
        trustlines_contract.transact({"from": A}).updateCreditline(B, -10)