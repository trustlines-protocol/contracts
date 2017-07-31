from ethereum import tester
import pytest, pprint, os

# setup accounts
value = 2
value1 = 3
system_fee_divisor = 1 / 0.001
capacity_fee_divisor = 1 / 0.002
imbalance_fee_divisor = 1 / 0.004

trustlines = [(0, 1, 100, 150, 15, 10),
              (1, 2, 200, 250, 25, 20),
              (2, 3, 100, 150, 15, 10),
              (3, 4, 200, 250, 25, 20),
              (4, 5, 100, 150, 15, 10),
              (5, 6, 200, 250, 25, 20),
              (6, 7, 100, 150, 15, 10),
              (7, 8, 200, 250, 25, 20)
              ]  # (A, B, tlAB, tlBA)


def annual_interest_rate_from_byte(di):
    assert di < 256
    if di == 0:
        return 0
    f = 1./(di * 256)
    return (1+f)**365 - 1

def annual_interest_rate_as_byte(ir):
    assert ir < 3.2
    if ir == 0:
        return 0
    return int(round(1 /((ir + 1)**(1/365.) -1) / 256))


def calc_system_fee(value3):
    return int(value3 / system_fee_divisor)

@pytest.fixture()
def trustlines_contract(chain):
    EternalStorage = chain.provider.get_contract_factory('EternalStorage')
    deploy_txn_hash = EternalStorage.deploy()
    eternalStorage_address = chain.wait.for_contract_address(deploy_txn_hash)

    Trustlines = chain.provider.get_contract_factory('CurrencyNetwork')
    deploy_txn_hash = Trustlines.deploy(args=[
        "Testcoin", "T", eternalStorage_address
    ])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    trustlines_contract = Trustlines(address=contract_address)
    for (A, B, tlAB, tlBA, irA, irB) in trustlines:
        trustlines_contract.transact({"from":chain.web3.eth.accounts[A]}).updateCreditline(chain.web3.eth.accounts[B], tlAB)
        trustlines_contract.transact({"from":chain.web3.eth.accounts[B]}).acceptCreditline(chain.web3.eth.accounts[A], tlAB)
        trustlines_contract.transact({"from":chain.web3.eth.accounts[B]}).updateCreditline(chain.web3.eth.accounts[A], tlBA)
        trustlines_contract.transact({"from":chain.web3.eth.accounts[A]}).acceptCreditline(chain.web3.eth.accounts[B], tlBA)
        trustlines_contract.transact({"from":chain.web3.eth.accounts[A]}).updateInterestRate(chain.web3.eth.accounts[B], irA)
        trustlines_contract.transact({"from":chain.web3.eth.accounts[B]}).updateInterestRate(chain.web3.eth.accounts[A], irB)
    return trustlines_contract

@pytest.fixture
def accounts(web3):
    def get(num):
        return [web3.eth.accounts[i] for i in range(num)]
    return get

def test_trustlines(trustlines_contract, web3):
    for (A, B, tlAB, tlBA, irA, irB) in trustlines:
        assert trustlines_contract.call().getCreditline(web3.eth.accounts[A], web3.eth.accounts[B]) == tlAB
        assert trustlines_contract.call().getCreditline(web3.eth.accounts[B], web3.eth.accounts[A]) == tlBA
        assert trustlines_contract.call().getAccount(web3.eth.accounts[A], web3.eth.accounts[B]) == [tlAB, tlBA, irA, irB, 0, 0, 0, 0]
        assert trustlines_contract.call().getInterestRate(web3.eth.accounts[A], web3.eth.accounts[B]) == irA
        assert trustlines_contract.call().getInterestRate(web3.eth.accounts[B], web3.eth.accounts[A]) == irB


def print_gas_used(state, string):
    t_gas = state.block.gas_used
    yield
    gas_used = state.block.gas_used - t_gas - 21000
    print(string, gas_used)

def test_transfer(trustlines_contract, accounts, state):
    (A, B, C, D) = accounts(4)
    # look for value above
    sysfee = calc_system_fee(value)
    print(value)
    with print_gas_used(state, 'gas direct transfer'):
        trustlines_contract.transact({"from":A}).transfer(B, value)
    assert trustlines_contract.call().getBalance(A, B) == -value
    assert trustlines_contract.call().getInterestRate(A, B) == 15
    assert trustlines_contract.call().getInterestRate(B, A) == 10
    assert trustlines_contract.call().getFeesOutstanding(A, B) == sysfee
    assert trustlines_contract.call().getFeesOutstanding(B, A) == 0
    trustlines_contract.transact({"from":B}).transfer(C, value)
    trustlines_contract.transact({"from":C}).transfer(D, value)
    assert trustlines_contract.call().getInterestRate(B, C) == 25
    assert trustlines_contract.call().getInterestRate(C, B) == 20
    assert trustlines_contract.call().getInterestRate(C, D) == 15
    assert trustlines_contract.call().getInterestRate(D, C) == 10
    assert trustlines_contract.call().getBalance(B, C) == -value
    assert trustlines_contract.call().getBalance(C, D) == -value
    assert trustlines_contract.call().getFeesOutstanding(B, C) == sysfee
    assert trustlines_contract.call().getFeesOutstanding(C, D) == sysfee


def test_transfer_with_interest(trustlines_contract, accounts):
    (A, B) = accounts(2)
    trustlines_contract.transact({"from":A}).transfer(B, value)
    assert trustlines_contract.call().getBalance(A, B) == -value
    print("bal:", trustlines_contract.call().getBalance(A, B))
    print("ir:", trustlines_contract.call().getInterestRate(A, B))

    # Forwarding by a 100 days
    occurred_interest = trustlines_contract.call().occurredInterest(A, B, 150)
    assert occurred_interest == 7800
    occurred_interest = 0
    # look for value1 above
    trustlines_contract.transact({"from":A}).transfer(B, value1)
    # Subtracting interest because B is smaller than A in this case
    assert trustlines_contract.call().getBalance(A, B) == -value -value1 - occurred_interest
    assert trustlines_contract.call().getBalance(B, A) == value + value1 + occurred_interest


# Test mediated transfer without considering or applying interest considering increase in the imbalance between B and C
def test_mediated_transfer_without_interest(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    sysfee = calc_system_fee(value)
    trustlines_contract.transact({"from":A}).transfer(B, value)
    trustlines_contract.transact({"from":B}).transfer(C, value)
    imbalance_fee = trustlines_contract.call().imbalanceFee(B, C, value)
    capacity_fee = trustlines_contract.call().capacityFee(value)
    deducted_fee = trustlines_contract.call().deductedTransferFees(B, C, value)
    new_value = value
    new_value -= deducted_fee
    path = [B, C]
    assert deducted_fee == capacity_fee + imbalance_fee
    trustlines_contract.transact({"from": A}).prepare(C, value, 100, path)
    trustlines_contract.transact({"from": A}).mediatedTransfer(C, value)
    assert trustlines_contract.call().getFeesOutstanding(A, B) == 2 * sysfee
    assert trustlines_contract.call().getBalance(A, B) == -2 * value
    assert trustlines_contract.call().getBalance(B, C) ==  -value - new_value


# Test mediated transfer without applying interest considering reduction in imbalance between B and C
def test_mediated_transfer_imbalance_reduced(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    sysfee = calc_system_fee(value)
    sysfee1 = calc_system_fee(value1)
    trustlines_contract.transact({"from": A}).transfer(B, value1)
    trustlines_contract.transact({"from": C}).transfer(B, value1)
    trustlines_contract.call().getBalance(A, B) == -value1
    trustlines_contract.call().getBalance(B, C) == value1
    imbalance_fee = trustlines_contract.call().imbalanceFee(B, C, value)
    capacity_fee = trustlines_contract.call().capacityFee(value)
    deducted_fee = trustlines_contract.call().deductedTransferFees(B, C, value)
    new_value = value
    new_value -= deducted_fee
    assert deducted_fee == capacity_fee + imbalance_fee
    # This time imbalance between B--C hop is reduced hence imbalancefee should be zero
    assert imbalance_fee == 0
    path = [B, C]
    trustlines_contract.transact({"from": A}).prepare(C, value, 100, path)
    trustlines_contract.transact({"from": A}).mediatedTransfer(C, value)
    assert trustlines_contract.call().getFeesOutstanding(A, B) == sysfee + sysfee1
    assert trustlines_contract.call().getBalance(A, B) == -value1 -value
    assert trustlines_contract.call().getBalance(B, C) == value1 - new_value


# Test mediated transfer without interest where balance between B and C
# goes from positive to negative and again introduces imbalance
def test_mediated_transfer_imbalance_increased(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    sysfee = calc_system_fee(value)
    sysfee1 = calc_system_fee(value1)
    trustlines_contract.transact({"from": A}).transfer(B, value)
    trustlines_contract.transact({"from": C}).transfer(B, value)
    assert trustlines_contract.call().getBalance(A, B) == -value
    assert trustlines_contract.call().getBalance(B, C) == value
    imbalance_fee = trustlines_contract.call().imbalanceFee(B, C, value1)
    capacity_fee = trustlines_contract.call().capacityFee(value1)
    deducted_fee = trustlines_contract.call().deductedTransferFees(B, C, value1)
    new_value = value1
    new_value -= deducted_fee
    assert deducted_fee == capacity_fee + imbalance_fee
    path = [B, C]
    trustlines_contract.transact({"from": A}).prepare(C, value1, 100, path)
    trustlines_contract.transact({"from": A}).mediatedTransfer(C, value1)
    assert trustlines_contract.call().getFeesOutstanding(A, B) == sysfee + sysfee1
    assert trustlines_contract.call().getBalance(A, B) == -value - value1
    assert trustlines_contract.call().getBalance(B, C) == value - new_value


def test_mediated_transfer_with_interest(trustlines_contract, accounts):
    (A, B, C) = accounts(3)
    sysfee = calc_system_fee(value)
    trustlines_contract.transact({"from": A}).transfer(B, value)
    trustlines_contract.transact({"from": B}).transfer(C, value)
    assert trustlines_contract.call().getBalance(A, B) == -value
    assert trustlines_contract.call().getBalance(B, C) == -value
    tester.state().block.timestamp += 100 * 24 * 60 * 60
    imbalance_fee = trustlines_contract.call().imbalanceFee(B, C, value)
    capacity_fee = trustlines_contract.call().capacityFee(value)
    #deducted_fee = trustlines_contract.call().deductedTransferFees(B, C, value)
    #assert imbalance_fee == 800
    #assert capacity_fee == 400
    #assert deducted_fee == 1200
    new_value = value
    #new_value -= deducted_fee
    path = [B, C]
    occurred_interestAB = trustlines_contract.call().occurredInterest(A, B, trustlines_contract.call().calculateMtime())
    occurred_interestBC = trustlines_contract.call().occurredInterest(B, C, trustlines_contract.call().calculateMtime())
    trustlines_contract.transact({"from": A}).prepare(C, value, 100, path)
    trustlines_contract.transact({"from": A}).mediatedTransfer(C, value)
    assert trustlines_contract.call().getFeesOutstanding(A, B) == 2 * sysfee
    assert trustlines_contract.call().getBalance(A, B) == -value - value -occurred_interestAB
    assert trustlines_contract.call().getBalance(B, C) == -value -new_value + occurred_interestBC


def test_mediated_transfer_with_many_hops(trustlines_contract, accounts):
    (A, B, C, D, E, F, G, H, I) = accounts(9)
    sysfee = calc_system_fee(value)
    trustlines_contract.transact({"from": A}).transfer(B, value)
    trustlines_contract.transact({"from": B}).transfer(C, value)
    trustlines_contract.transact({"from": C}).transfer(D, value)
    trustlines_contract.transact({"from": D}).transfer(E, value)
    trustlines_contract.transact({"from": E}).transfer(F, value)
    trustlines_contract.transact({"from": F}).transfer(G, value)
    trustlines_contract.transact({"from": G}).transfer(H, value)
    trustlines_contract.transact({"from": H}).transfer(I, value)
    tester.state().block.timestamp += 100 * 24 * 60 * 60
    num_hops = 0
    path = [B]
    trustlines_contract.transact({"from": A}).prepare(B, value, 100, path)
    res = trustlines_contract.transact({"from": A}).mediatedTransfer(B, value)
    assert res

    num_hops += 1
    path = [B, C]
    trustlines_contract.transact({"from": A}).prepare(C, value, 100, path)
    res = trustlines_contract.transact({"from": A}).mediatedTransfer(C, value,)
    assert res

    num_hops += 1
    path = [B, C, D]
    trustlines_contract.transact({"from": A}).prepare(D, value, 100, path)
    res = trustlines_contract.transact({"from": A}).mediatedTransfer(D, value,)
    assert res

    num_hops += 1
    path = [B, C, D, E]
    trustlines_contract.transact({"from": A}).prepare(E, value, 100, path)
    res = trustlines_contract.transact({"from": A}).mediatedTransfer(E, value)
    assert res

    num_hops += 1
    path = [B, C, D, E, F]
    trustlines_contract.transact({"from": A}).prepare(F, value, 100, path)
    res = trustlines_contract.transact({"from": A}).mediatedTransfer(F, value)
    assert res

    num_hops += 1
    path = [B, C, D, E, F, G]
    trustlines_contract.transact({"from": A}).prepare(G, value, 100, path)
    res = trustlines_contract.transact({"from": A}).mediatedTransfer(G, value)
    assert res

    num_hops += 1
    path = [B, C, D, E, F, G, H]
    trustlines_contract.transact({"from": A}).prepare(H, value, 100, path)
    res = trustlines_contract.transact({"from": A}).mediatedTransfer(H, value)
    assert res