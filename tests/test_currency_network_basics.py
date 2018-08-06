import pytest
from ethereum import tester
from web3.exceptions import BadFunctionCallOutput


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
    contract.transact().init('TestCoin', 'T', 6, 0, 0, False, False)

    return contract


@pytest.fixture()
def currency_network_contract_with_trustlines(currency_network_contract, accounts):
    contract = currency_network_contract
    for (A, B, clAB, clBA) in trustlines:
        contract.transact().setAccount(accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0)
    return contract


@pytest.fixture()
def currency_network_contract_custom_interest(chain):
    CurrencyNetworkFactory = chain.provider.get_contract_factory('CurrencyNetwork')
    deploy_txn_hash = CurrencyNetworkFactory.deploy(args=[])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    contract = CurrencyNetworkFactory(address=contract_address)
    contract.transact().init(_name='TestCoin', _symbol='T', _decimals=6, _capacityImbalanceFeeDivisor=0,
                             _defaultInterests=0, _customInterests=True, _safeInterestRippling=False)
    return contract


def test_meta_name(currency_network_contract):
    assert currency_network_contract.call().name() == 'TestCoin'


def test_meta_symbol(currency_network_contract):
    assert currency_network_contract.call().symbol() == 'T'


def test_meta_decimal(currency_network_contract):
    assert currency_network_contract.call().decimals() == 6


def test_users(currency_network_contract_with_trustlines, accounts):
    A, B, C, D, E, *rest = accounts
    assert set(currency_network_contract_with_trustlines.call().getUsers()) == {A, B, C, D, E}


def test_friends(currency_network_contract_with_trustlines, accounts):
    A, B, C, D, E, *rest = accounts
    assert set(currency_network_contract_with_trustlines.call().getFriends(A)) == {B, E}


def test_set_get_Account(currency_network_contract, accounts):
    contract = currency_network_contract
    contract.transact().init('TestCoin', 'T', 6, 0, 0, True, False)
    contract.transact().setAccount(accounts[0], accounts[1], 10, 20, 2, 3, 100, 200, 0, 4)
    assert contract.call().getAccount(accounts[0], accounts[1]) == [10, 20, 2, 3, 100, 200, 0, 4]
    assert contract.call().getAccount(accounts[1], accounts[0]) == [20, 10, 3, 2, 200, 100, 0, -4]
    contract.transact().setAccount(accounts[1], accounts[0], 10, 20, 2, 3, 100, 200, 0, 4)
    assert contract.call().getAccount(accounts[1], accounts[0]) == [10, 20, 2, 3, 100, 200, 0, 4]
    assert contract.call().getAccount(accounts[0], accounts[1]) == [20, 10, 3, 2, 200, 100, 0, -4]


def test_set_get_Account_default_interests(currency_network_contract, accounts):
    contract = currency_network_contract
    contract.transact().setAccountDefaultInterests(accounts[0], accounts[1], 10, 20, 100, 200, 0, 4)
    # setAccount(address, address, creditLimit, creditLimit, interest, interest, feeOut, feeOut, mtime, balance)
    assert contract.call().getAccount(accounts[0], accounts[1]) == [10, 20, 0, 0, 100, 200, 0, 4]
    assert contract.call().getAccount(accounts[1], accounts[0]) == [20, 10, 0, 0, 200, 100, 0, -4]
    contract.transact().setAccountDefaultInterests(accounts[1], accounts[0], 10, 20, 100, 200, 0, 4)
    assert contract.call().getAccount(accounts[1], accounts[0]) == [10, 20, 0, 0, 100, 200, 0, 4]
    assert contract.call().getAccount(accounts[0], accounts[1]) == [20, 10, 0, 0, 200, 100, 0, -4]


def test_balance(currency_network_contract, accounts):
    contract = currency_network_contract
    contract.transact().setAccount(accounts[0], accounts[1], 10, 20, 0, 0, 100, 200, 0, 4)
    assert contract.call().balance(accounts[0], accounts[1]) == 4
    assert contract.call().balance(accounts[1], accounts[0]) == -4


def test_transfer_0_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 110, 0, [accounts[1]])
    assert contract.call().balance(accounts[0], accounts[1]) == -110


def test_transfer_0_mediators_fail_not_enough_credit(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[1], 151, 0, [accounts[1]])


def test_transfer_0_mediators_fail_wrong_path(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[1], 110, 0, [accounts[2]])
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[2], 1, 0, [accounts[1]])


def test_transfer_1_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.transact({'from': accounts[0]}).transfer(accounts[2], 110, 0, [accounts[1], accounts[2]])
    assert contract.call().balance(accounts[0], accounts[1]) == -110
    assert contract.call().balance(accounts[2], accounts[1]) == 110


def test_transfer_1_mediators_not_enough_credit(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[2], 151, 0, [accounts[1], accounts[2]])


def test_transfer_1_mediators_not_enough_wrong_path(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(tester.TransactionFailed):
        contract.transact({'from': accounts[0]}).transfer(accounts[2], 110, 0, [accounts[1], accounts[3]])


def test_transfer_3_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.transact({'from': accounts[0]}).transfer(accounts[4], 110, 0, [accounts[1],
                                                                            accounts[2],
                                                                            accounts[3],
                                                                            accounts[4]])
    assert contract.call().balance(accounts[0], accounts[1]) == -110
    assert contract.call().balance(accounts[1], accounts[2]) == -110
    assert contract.call().balance(accounts[2], accounts[3]) == -110
    assert contract.call().balance(accounts[4], accounts[3]) == 110


def test_transfer_payback(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.transact({'from': accounts[0]}).transfer(accounts[4], 110, 0, [accounts[1],
                                                                            accounts[2],
                                                                            accounts[3],
                                                                            accounts[4]])
    contract.transact({'from': accounts[4]}).transfer(accounts[0], 110, 0, [accounts[3],
                                                                            accounts[2],
                                                                            accounts[1],
                                                                            accounts[0]])
    assert contract.call().balance(accounts[0], accounts[1]) == 0
    assert contract.call().balance(accounts[1], accounts[2]) == 0
    assert contract.call().balance(accounts[2], accounts[3]) == 0
    assert contract.call().balance(accounts[4], accounts[3]) == 0


def test_send_back(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.call().balance(accounts[0], accounts[1]) == 0
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 120, 0, [accounts[1]])
    assert contract.call().balance(accounts[1], accounts[0]) == 120
    contract.transact({'from': accounts[1]}).transfer(accounts[0], 120, 0, [accounts[0]])
    assert contract.call().balance(accounts[0], accounts[1]) == 0


def test_send_more(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.call().balance(accounts[0], accounts[1]) == 0
    contract.transact({'from': accounts[0]}).transfer(accounts[1], 120, 0, [accounts[1]])
    assert contract.call().balance(accounts[1], accounts[0]) == 120
    contract.transact({'from': accounts[1]}).transfer(accounts[0], 200, 0, [accounts[0]])
    assert contract.call().balance(accounts[0], accounts[1]) == 80


def test_update_without_accept_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 0, 0)
    assert contract.call().creditline(A, B) == 0
    assert contract.call().creditline(B, A) == 0
    assert contract.pastEvents('TrustlineUpdate').get() == []
    assert contract.pastEvents('TrustlineUpdateRequest').get()[0]['args']['_creditlineGiven'] == 50


def test_update_with_accept_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 0, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 0)
    assert contract.call().creditline(A, B) == 50
    assert contract.call().creditline(B, A) == 100
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditor'] == A
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditlineGiven'] == 50


def test_update_with_accept_different_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 0, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 49, 0, 0)
    assert contract.call().creditline(A, B) == 49
    assert contract.call().creditline(B, A) == 100
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditor'] == A


def test_update_with_accept_2nd_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 0, 0)
    contract.transact({"from": A}).updateTrustline(B, 50, 99, 0, 0)
    contract.transact({"from": B}).updateTrustline(A, 99, 50, 0, 0)
    assert contract.call().creditline(A, B) == 50
    assert contract.call().creditline(B, A) == 99
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditor'] == A
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditlineGiven'] == 50


def test_cannot_accept_old_trustline(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 0, 0)
    contract.transact({"from": A}).updateTrustline(B, 50, 99, 0, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 0)
    assert contract.call().creditline(A, B) == 0
    assert contract.call().creditline(B, A) == 0
    assert contract.pastEvents('TrustlineUpdate').get() == []


def test_update_reduce_need_no_accept_trustline(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.call().creditline(A, B) == 100
    assert contract.call().creditline(B, A) == 150
    contract.transact({"from": A}).updateTrustline(B, 99, 150, 0, 0)
    assert contract.call().creditline(A, B) == 99
    assert contract.call().creditline(B, A) == 150
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditlineGiven'] == 99


def test_update_without_accept_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)

    assert contract.call().interestRate(A, B) == 0
    assert contract.call().interestRate(B, A) == 0
    assert contract.pastEvents('TrustlineUpdate').get() == []
    assert contract.pastEvents('TrustlineUpdateRequest').get()[0]['args']['_interestRateGiven'] == 1


def test_update_with_accept_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 1)

    assert contract.call().interestRate(A, B) == 1
    assert contract.call().interestRate(B, A) == 0
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditor'] == A
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_interestRateGiven'] == 1


def test_update_with_accept_different_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 2)
    assert contract.call().interestRate(A, B) == 0
    assert contract.call().interestRate(B, A) == 0
    assert contract.pastEvents('TrustlineUpdate').get() == []


def test_update_with_accept_2nd_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 2, 0)
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 1)
    assert contract.call().interestRate(A, B) == 1
    assert contract.call().interestRate(B, A) == 0
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_creditor'] == A
    assert contract.pastEvents('TrustlineUpdate').get()[0]['args']['_interestRateGiven'] == 1


def test_cannot_accept_old_trustline_interests(currency_network_contract_custom_interest, accounts):
    contract = currency_network_contract_custom_interest

    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 2, 0)
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 2)
    assert contract.call().interestRate(A, B) == 0
    assert contract.call().interestRate(B, A) == 0
    assert contract.pastEvents('TrustlineUpdate').get() == []


def test_update_trustline_with_custom_while_forbidden(currency_network_contract, accounts):
    '''Verifies that if the network uses default interests of 0, no custom interests can be put'''
    contract = currency_network_contract

    A, B, *rest = accounts
    with pytest.raises(tester.TransactionFailed):
        contract.transact({"from": A}).updateTrustline(B, 50, 100, 2, 1)


def test_update_trustline_with_custom_while_forbidden_lowering_interests(currency_network_contract, accounts):
    '''Verifies that if the network uses default interests of 0, no custom interests can be put'''
    contract = currency_network_contract
    contract.transact().init('TestCoin', 'T', 6, 0, 5, False, False)

    A, B, *rest = accounts
    contract.transact().setAccountDefaultInterests(A, B, 200, 200, 0, 0, 0, 0)

    with pytest.raises(tester.TransactionFailed):
        contract.transact({"from": A}).updateTrustline(B, 50, 100, 1, 1)


def test_spendable(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.call().spendableTo(A, B) == 150
    assert contract.call().spendableTo(B, A) == 100
    contract.transact({"from": A}).transfer(B, 40, 0, [B])
    assert contract.call().spendableTo(A, B) == 110
    assert contract.call().spendableTo(B, A) == 140


def test_balance_of(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    assert contract.call().balanceOf(A) == 700
    contract.transact({"from": A}).transfer(B, 40, 0, [B])
    assert contract.call().balanceOf(A) == 660
    contract.transact({"from": A}).transfer(C, 20, 0, [E, D, C])
    assert contract.call().balanceOf(A) == 640


def test_total_supply(currency_network_contract_with_trustlines):
    assert currency_network_contract_with_trustlines.call().totalSupply() == 3250


def test_balance_event(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    contract.transact({'from': A}).transfer(B, 110, 0, [B])
    events = contract.pastEvents('BalanceUpdate').get()
    assert len(events) == 1
    args = events[0]['args']
    from_ = args['_from']
    to = args['_to']
    value = args['_value']
    if from_ == A and to == B:
        assert value == -110
    elif from_ == B and to == A:
        assert value == 110
    else:
        assert False, 'Wrong _from and _to in the event: were: {}, {}, but expected: {}, {}'.format(from_, to, A, B)


def test_transfer_event(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    contract.transact({'from': A}).transfer(B, 110, 0, [B])
    events = contract.pastEvents('Transfer').get()
    assert len(events) == 1
    args = events[0]['args']
    from_ = args['_from']
    to = args['_to']
    value = args['_value']
    assert from_ == A
    assert to == B
    assert value == 110


def test_update_trustline_add_users(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.transact({"from": A}).updateTrustline(B, 50, 100, 0, 0)
    contract.transact({"from": B}).updateTrustline(A, 100, 50, 0, 0)
    assert len(contract.call().getUsers()) == 2


def test_update_set_account_add_users(currency_network_contract, accounts):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.transact().setAccount(A, B, 50, 100, 0, 0, 0, 0, 0, 0)
    assert len(contract.call().getUsers()) == 2


def test_selfdestruct(currency_network_contract):
    currency_network_contract.transact().destruct()
    with pytest.raises(BadFunctionCallOutput):  # contract does not exist
        currency_network_contract.call().decimals()


def test_only_owner_selfdestruct(currency_network_contract, accounts):
    with pytest.raises(tester.TransactionFailed):
        currency_network_contract.transact({"from": accounts[1]}).destruct()
