import pytest
from ethereum import tester


trustlines = [(0, 1, 2000000000, 2000000000),
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
    contract.transact().init('TestCoin', 'T', 6, 0, 0, False, False)
    # init(name, symbol, decimal, feeDivisor, defaultInterest, customInterests, safeInterestRippling)
    return contract


@pytest.fixture()
def currency_network_contract_with_trustlines(currency_network_contract, accounts):
    contract = currency_network_contract
    for (A, B, clAB, clBA) in trustlines:
        contract.transact().setAccount(accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0)
        # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)
    return contract


@pytest.fixture()
def currency_network_contract_custom_interests_safe_ripple(chain):
    CurrencyNetworkFactory = chain.provider.get_contract_factory('CurrencyNetwork')
    deploy_txn_hash = CurrencyNetworkFactory.deploy(args=[])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    contract = CurrencyNetworkFactory(address=contract_address)
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, True)
    # init(name, symbol, decimal, feeDivisor, defaultInterest, customInterests, safeInterestRippling)
    return contract


def test_interests_default(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests interests with a default setting'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 1000, False, False)

    chain.rpc_methods.testing_timeTravel(1442509455)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 100000000, 2000000, [accounts[1]])

    chain.rpc_methods.testing_timeTravel(1442509455 + 60*60*24*365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == -100000000*1.01 - 1


def test_interests_default_high_value(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests interests with a default setting with a different value'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 20000, False, False)

    contract.transact().setAccount(accounts[0], accounts[1], 2000000000, 2000000000, 20000, 20000, 0, 0, 1442509455,
                                   100000000)

    chain.rpc_methods.testing_timeTravel(1442509455 + 60*60*24*365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == 100000000*1.20 - 1


def test_interests_positive_balance(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests interests with a default setting with a negative balance'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 1000, False, False)

    contract.transact().setAccount(accounts[0], accounts[1], 2000000000, 2000000000, 1000, 1000, 0, 0, 1442509455,
                                   100000000)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == 100000000 * 1.01 - 1


def test_no_interests(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests that we can have a network with no interests'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 0, False, False)

    chain.rpc_methods.testing_timeTravel(1442509455)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 100000000, 2000000, [accounts[1]])

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == -100000000 - 1


def test_custom_interests(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests custom interests setting, set with setAccount'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)
    contract.transact().setAccount(accounts[0], accounts[1], 0, 2000000000, 0, 12345, 0, 0, 0, 0)

    chain.rpc_methods.testing_timeTravel(1442509455)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 100000000, 2000000, [accounts[1]])

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == -100000000 * 1.12345 - 1


def test_custom_interests_postive_balance(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests custom interests setting, set with setAccount'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)
    contract.transact().setAccount(accounts[0], accounts[1], 0, 2000000000, 12345, 0, 0, 0, 1442509455, 100000000)

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == 100000000 * 1.12345 - 1


def test_setting_default_and_custom_interests_fails(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests that we cannot set default and custom interests at the same time'''

    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact().init('TestCoin', 'T', 6, 0, 1, True, False)


def test_safe_interest_allows_direct_transactions(currency_network_contract_custom_interests_safe_ripple, accounts,
                                                  chain):
    '''Tests that the safeInterestRippling does not prevent legit transactions'''

    contract = currency_network_contract_custom_interests_safe_ripple
    contract.transact().setAccount(accounts[0], accounts[1], 1000000, 2000000, 1000, 2000, 0, 0, 0, 0)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])


def test_safe_interest_allows_transactions_mediated(currency_network_contract_custom_interests_safe_ripple, accounts,
                                                    chain):
    '''Tests that the safeInterestRippling does not prevent legit transactions'''

    contract = currency_network_contract_custom_interests_safe_ripple
    contract.transact().setAccount(accounts[0], accounts[1], 1000000, 2000000, 1000, 2000, 0, 0, 0, 0)
    contract.transact().setAccount(accounts[1], accounts[2], 1000000, 2000000, 1000, 2000, 0, 0, 0, 0)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    contract.transact({'from': accounts[0]}).transfer(accounts[2], 1, 2, [accounts[1], accounts[2]])


def test_safe_interest_disallows_transactions_mediated(currency_network_contract_custom_interests_safe_ripple,
                                                       accounts, chain):
    '''Tests that the safeInterestRippling prevents certain transactions'''

    contract = currency_network_contract_custom_interests_safe_ripple
    contract.transact().setAccount(accounts[0], accounts[1], 1000000, 2000000, 2000, 1000, 0, 0, 0, 1)
    contract.transact().setAccount(accounts[1], accounts[2], 1000000, 2000000, 1000, 2000, 0, 0, 0, 1)

    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[2], 1, 2, [accounts[1], accounts[2]])


def test_safe_interest_allows_transactions_mediated_solves_imbalance(
        currency_network_contract_custom_interests_safe_ripple, accounts, chain):
    '''Tests that the safeInterestRippling allows transactions that reduce imbalances'''

    contract = currency_network_contract_custom_interests_safe_ripple
    contract.transact().setAccount(accounts[0], accounts[1], 1000000, 2000000, 2000, 1000, 0, 0, 0, 100)
    contract.transact().setAccount(accounts[1], accounts[2], 1000000, 2000000, 1000, 2000, 0, 0, 0, 100)

    contract.transact({'from': accounts[0]}).transfer(accounts[2], 1, 2, [accounts[1], accounts[2]])


def test_safe_interest_disallows_transactions_mediated_solves_imbalance_but_overflows(
        currency_network_contract_custom_interests_safe_ripple, accounts, chain):
    '''Tests that the safeInterestRippling allows transactions that reduce imbalances'''

    contract = currency_network_contract_custom_interests_safe_ripple
    contract.transact().setAccount(accounts[0], accounts[1], 1000000, 2000000, 2000, 1000, 0, 0, 0, 100)
    contract.transact().setAccount(accounts[1], accounts[2], 1000000, 2000000, 1000, 2000, 0, 0, 0, 100)

    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[2], 101, 2, [accounts[1], accounts[2]])


def test_negative_interests_default_positive_balance(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests interests with a default setting with a negative balance'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, -1000, False, False)

    contract.transact().setAccount(accounts[0], accounts[1], 2000000000, 2000000000, -1000, -1000, 0, 0, 1442509455,
                                   100000000)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == 100000000 * 0.99 - 1


def test_negative_interests_default_negative_balance(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests interests with a default setting with a negative balance'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, -1000, False, False)

    contract.transact().setAccount(accounts[0], accounts[1], 2000000000, 2000000000, -1000, -1000, 0, 0, 1442509455,
                                   -100000000)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == -100000000 * 0.99 - 1


def test_negative_interests_custom_positive_balance(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests interests with a default setting with a negative balance'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)

    contract.transact().setAccount(accounts[0], accounts[1], 2000000000, 2000000000, -1000, -1000, 0, 0, 1442509455,
                                   100000000)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == 100000000 * 0.99 - 1


def test_negative_interests_custom_negative_balance(currency_network_contract_with_trustlines, accounts, chain):
    '''Tests interests with a default setting with a negative balance'''

    contract = currency_network_contract_with_trustlines
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)

    contract.transact().setAccount(accounts[0], accounts[1], 2000000000, 2000000000, -1000, -1000, 0, 0, 1442509455,
                                   -100000000)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)

    chain.rpc_methods.testing_timeTravel(1442509455 + 60 * 60 * 24 * 365)
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 1, 2, [accounts[1]])

    assert contract.call().balance(accounts[0], accounts[1]) == -100000000 * 0.99 - 1
