import time

import pytest
from ethereum import tester

from tlcontracts.exchange import Order
from tlcontracts.signing import priv_to_pubkey


trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, clAB, clBA)


NULL_ADDRESS = '0x0000000000000000000000000000000000000000'


@pytest.fixture()
def exchange_contract(chain):
    ExchangeFactory = chain.provider.get_contract_factory('Exchange')
    deploy_txn_hash = ExchangeFactory.deploy(args=[])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    contract = ExchangeFactory(address=contract_address)

    return contract


@pytest.fixture()
def currency_network_contract(chain):
    CurrencyNetworkFactory = chain.provider.get_contract_factory('CurrencyNetwork')
    deploy_txn_hash = CurrencyNetworkFactory.deploy(args=[])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    contract = CurrencyNetworkFactory(address=contract_address)
    contract.transact().init('TestCoin', 'T', 6, 0)

    return contract


@pytest.fixture()
def token_contract(chain, accounts):
    A, B, C, *rest = accounts
    TokenFactory = chain.provider.get_contract_factory('DummyToken')
    deploy_txn_hash = TokenFactory.deploy(args=['DummyToken', 'DT', 18, 10000000])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    contract = TokenFactory(address=contract_address)
    contract.transact().setBalance(A, 10000)
    contract.transact().setBalance(B, 10000)
    contract.transact().setBalance(C, 10000)
    return contract


@pytest.fixture()
def currency_network_contract_with_trustlines(currency_network_contract, exchange_contract, accounts):
    contract = currency_network_contract
    for (A, B, clAB, clBA) in trustlines:
        contract.transact().setAccount(accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0)
    contract.transact().addAuthorizedAddress(exchange_contract.address)
    return contract


def test_order_hash(exchange_contract, token_contract, currency_network_contract_with_trustlines, accounts):
    maker_address, taker_address, *rest = accounts

    order = Order(exchange_contract.address,
                  maker_address,
                  NULL_ADDRESS,
                  token_contract.address,
                  currency_network_contract_with_trustlines.address,
                  NULL_ADDRESS,
                  100,
                  50,
                  0,
                  0,
                  1234,
                  1234
                  )

    assert order.hash() == exchange_contract.call().getOrderHash(
        [order.maker_address,
         order.taker_address,
         order.maker_token,
         order.taker_token,
         order.fee_recipient],
        [order.maker_token_amount,
         order.taker_token_amount,
         order.maker_fee,
         order.taker_fee,
         order.expiration_timestamp_in_sec,
         order.salt]
    ).encode('Latin-1')


def test_order_signature(exchange_contract, token_contract, currency_network_contract_with_trustlines, accounts):
    maker_address, taker_address, *rest = accounts

    order = Order(exchange_contract.address,
                  maker_address,
                  NULL_ADDRESS,
                  token_contract.address,
                  currency_network_contract_with_trustlines.address,
                  NULL_ADDRESS,
                  100,
                  50,
                  0,
                  0,
                  1234,
                  1234
                  )

    v, r, s = order.sign(tester.k0)

    assert exchange_contract.call().isValidSignature(maker_address, order.hash(), v, r, s)


def test_exchange(exchange_contract, token_contract, currency_network_contract_with_trustlines, accounts):
    maker_address, mediator_address, taker_address, *rest = accounts

    assert token_contract.call().balanceOf(maker_address) == 10000
    assert token_contract.call().balanceOf(taker_address) == 10000
    assert currency_network_contract_with_trustlines.call().balance(maker_address, mediator_address) == 0
    assert currency_network_contract_with_trustlines.call().balance(mediator_address, taker_address) == 0

    token_contract.transact({'from': maker_address}).approve(exchange_contract.address, 100)

    order = Order(exchange_contract.address,
                  maker_address,
                  NULL_ADDRESS,
                  token_contract.address,
                  currency_network_contract_with_trustlines.address,
                  NULL_ADDRESS,
                  100,
                  50,
                  0,
                  0,
                  int(time.time()+60*60*24),
                  1234
                  )

    assert priv_to_pubkey(tester.k0) == maker_address

    v, r, s = order.sign(tester.k0)

    exchange_contract.transact({'from': taker_address}).fillOrderTrustlines(
          [order.maker_address, order.taker_address, order.maker_token, order.taker_token, order.fee_recipient],
          [order.maker_token_amount, order.taker_token_amount, order.maker_fee,
           order.taker_fee, order.expiration_timestamp_in_sec, order.salt],
          50,
          [],
          [mediator_address, maker_address],
          v,
          r,
          s)

    assert token_contract.call().balanceOf(maker_address) == 9900
    assert token_contract.call().balanceOf(taker_address) == 10100
    assert currency_network_contract_with_trustlines.call().balance(maker_address, mediator_address) == 50
    assert currency_network_contract_with_trustlines.call().balance(taker_address, mediator_address) == -50
