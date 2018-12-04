# This file has been copied and adapted from the trustlines-contracts project.
# We like to get rid of the populus dependency and we don't want to compile the
# contracts when running tests in this project.

import os
import sys
import json
import collections
from web3 import Web3
from web3.utils.threads import (
    Timeout,
)


def load_contracts_json():
    path = (os.environ.get("TRUSTLINES_CONTRACTS_JSON")
            or os.path.join(sys.prefix,
                            'trustlines-contracts',
                            'build',
                            'contracts.json'))
    with open(path, "rb") as f:
        return json.load(f)


# lazily load the contracts, so the compile_contracts fixture has a chance to
# set TRUSTLINES_CONTRACTS_JSON

class LazyContractsLoader(collections.UserDict):
    def __getitem__(self, *args):
        if not self.data:
            self.data = load_contracts_json()
        return super().__getitem__(*args)


contracts = LazyContractsLoader()


class TransactionFailed(Exception):
    pass


def wait_for_transaction_receipt(web3, txid, timeout=180):
    with Timeout(timeout) as time:
            while not web3.eth.getTransactionReceipt(txid):
                time.sleep(5)

    return web3.eth.getTransactionReceipt(txid)


def check_successful_tx(web3: Web3, txid: str, timeout=180) -> dict:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt
    """
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    tx_info = web3.eth.getTransaction(txid)
    status = receipt.get("status", None)
    if receipt["gasUsed"] == tx_info["gas"] or status is False:
        raise TransactionFailed
    return receipt


def wait(transfer_filter):
    with Timeout(30) as timeout:
        while not transfer_filter.get(False):
            timeout.sleep(2)


def get_contract_factory(web3, contract_name):
    contract_interface = contracts[contract_name]
    return web3.eth.contract(
        abi=contract_interface["abi"], bytecode=contract_interface["bytecode"]
    )


def deploy(contract_name, web3, *args):
    contract = get_contract_factory(web3, contract_name)
    txhash = contract.constructor(*args).transact()
    receipt = check_successful_tx(web3, txhash)
    id_address = receipt["contractAddress"]
    return contract(id_address)


# def contract(contract_name, address, chain):
#     return chain.provider.get_contract_factory(contract_name)(address)


def deploy_exchange(web3):
    exchange = deploy("Exchange", web3)
    return exchange


def deploy_unw_eth(web3, exchange_address=None):
    unw_eth = deploy("UnwEth", web3)
    if exchange_address is not None:
        if exchange_address is not None:
            txid = unw_eth.functions.addAuthorizedAddress(exchange_address).transact(
                {"from": web3.eth.accounts[0]})
            check_successful_tx(web3, txid)
    return unw_eth


def deploy_network(
    web3,
    name,
    symbol,
    decimals,
    fee_divisor=0,
    default_interest_rate=0,
    custom_interests=True,
    prevent_mediator_interests=False,
    exchange_address=None,
    currency_network_contract_name=None
):
    # CurrencyNetwork is the standard contract to deploy, If we're running
    # tests or trying to export data for testing the python implementation of
    # private functions, we may want deploy the TestCurrencyNetwork contract
    # instead.
    if currency_network_contract_name is None:
        currency_network_contract_name = "CurrencyNetwork"
    currency_network = deploy(currency_network_contract_name, web3)

    txid = currency_network.functions.init(name,
                                           symbol,
                                           decimals,
                                           fee_divisor,
                                           default_interest_rate,
                                           custom_interests,
                                           prevent_mediator_interests).transact(
        {"from": web3.eth.accounts[0]})
    check_successful_tx(web3, txid)
    if exchange_address is not None:
        txid = currency_network.functions.addAuthorizedAddress(exchange_address).transact(
            {"from": web3.eth.accounts[0]})
        check_successful_tx(web3, txid)

    return currency_network


def deploy_proxied_network(web3, name, symbol, decimals, fee_divisor=100, exchange_address=None):
    raise NotImplementedError
    currency_network = deploy("CurrencyNetwork", web3)
    currency_network_address = currency_network.address
    resolver = deploy("Resolver", web3, currency_network_address)
    proxy = deploy("EtherRouter", web3, resolver.address)
    proxied_trustlines = get_contract_factory(web3, "CurrencyNetwork")(proxy.address)
    txid = proxied_trustlines.functions.init(name, symbol, decimals, fee_divisor).transact()
    check_successful_tx(web3, txid)
    if exchange_address is not None:
        txid = proxied_trustlines.functions.addAuthorizedAddress(exchange_address).transact()
        check_successful_tx(web3, txid)

    txid = resolver.functions.registerLengthFunction(
        "getUsers()",
        "getUsersReturnSize()",
        currency_network_address).transact()
    check_successful_tx(web3, txid)
    txid = resolver.functions.registerLengthFunction(
        "getFriends(address)",
        "getFriendsReturnSize(address)",
        currency_network_address).transact()
    check_successful_tx(web3, txid)
    txid = resolver.functions.registerLengthFunction(
        "getAccount(address,address)",
        "getAccountLen()",
        currency_network_address).transact()
    check_successful_tx(web3, txid)
    txid = resolver.functions.registerLengthFunction(
        "name()", "nameLen()",
        currency_network_address).transact()
    check_successful_tx(web3, txid)
    txid = resolver.functions.registerLengthFunction(
        "symbol()", "symbolLen()",
        currency_network_address).transact()
    check_successful_tx(web3, txid)
    return proxied_trustlines


def deploy_networks(web3, network_settings, currency_network_contract_name=None):
    exchange = deploy_exchange(web3)
    unw_eth = deploy_unw_eth(web3, exchange.address)

    networks = [
        deploy_network(
            web3,
            exchange_address=exchange.address,
            currency_network_contract_name=currency_network_contract_name,
            **network_setting,
        )
        for network_setting in network_settings
    ]

    return networks, exchange, unw_eth
