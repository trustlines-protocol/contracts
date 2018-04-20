import pytest
from ethereum import tester


trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, clAB, clBA)


@pytest.fixture()
def currency_network_contract(chain):
    CurrencyNetworkFactory = chain.provider.get_contract_factory('CurrencyNetwork')
    deploy_txn_hash = CurrencyNetworkFactory.deploy(args=[])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    contract = CurrencyNetworkFactory(address=contract_address)
    contract.transact().init('TestCoin', 'T', 6, 100)

    return contract


@pytest.fixture()
def currency_network_contract_with_trustlines(currency_network_contract, accounts):
    contract = currency_network_contract
    for (A, B, clAB, clBA) in trustlines:
        contract.transact().setAccount(accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0)
    return contract


def test_transfer_0_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 100, 2, [accounts[1]])
    assert contract.call().balance(accounts[0], accounts[1]) == -100 - 2


def test_transfer_0_mediators_fail_not_enough_credit(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[1], 151 - 2, 2, [accounts[1]])


def test_transfer_1_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.transact({'from': accounts[0]}).transfer(accounts[2], 50, 2, [accounts[1], accounts[2]])
    assert contract.call().balance(accounts[0], accounts[1]) == -50 - 2
    assert contract.call().balance(accounts[2], accounts[1]) == 50 + 1


def test_transfer_1_mediators_not_enough_credit(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[2], 151 - 2, 2, [accounts[1], accounts[2]])


def test_transfer_3_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.transact({'from': accounts[0]}).transfer(accounts[4], 100, 8, [accounts[1],
                                                                            accounts[2],
                                                                            accounts[3],
                                                                            accounts[4]])
    assert contract.call().balance(accounts[0], accounts[1]) == -100 - 8
    assert contract.call().balance(accounts[1], accounts[2]) == -100 - 6
    assert contract.call().balance(accounts[2], accounts[3]) == -100 - 4
    assert contract.call().balance(accounts[4], accounts[3]) == 100 + 2


def test_spendable(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.call().spendableTo(A, B) == 150
    assert contract.call().spendableTo(B, A) == 100
    contract.transact({"from": A}).transfer(B, 40, 1, [B])
    assert contract.call().spendableTo(A, B) == 110 - 1
    assert contract.call().spendableTo(B, A) == 140 + 1


def test_max_fee(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[1], 100, 1, [accounts[1]])


def test_send_back_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.call().balance(accounts[0], accounts[1]) == 0
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 120, 2, [accounts[1]])
    assert contract.call().balance(accounts[1], accounts[0]) == 120 + 2
    contract.transact({'from': accounts[1]}).transfer(accounts[0], 120, 0, [accounts[0]])
    assert contract.call().balance(accounts[0], accounts[1]) == 0 - 2


def test_send_more_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.call().balance(accounts[0], accounts[1]) == 0
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 120, 2, [accounts[1]])
    assert contract.call().balance(accounts[1], accounts[0]) == 120 + 2
    contract.transact({'from': accounts[1]}).transfer(accounts[0], 200, 1, [accounts[0]])
    assert contract.call().balance(accounts[0], accounts[1]) == 80 - 2 + 1
