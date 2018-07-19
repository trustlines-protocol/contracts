import os
import sys
from contextlib import contextmanager

from populus import Project
from populus.utils.wait import wait_for_transaction_receipt
from web3 import Web3
from web3.utils.compat import (
    Timeout,
)


class TransactionFailed(Exception):
    pass


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


def deploy(contract_name, chain, *args):
    contract = chain.provider.get_contract_factory(contract_name)
    txhash = contract.deploy(args=args)
    receipt = check_successful_tx(chain.web3, txhash)
    id_address = receipt["contractAddress"]
    return contract(id_address)


def contract(contract_name, address, chain):
    return chain.provider.get_contract_factory(contract_name)(address)


def deploy_exchange(chain):
    exchange = deploy("Exchange", chain)
    return exchange


def deploy_unw_eth(chain, exchange_address=None):
    web3 = chain.web3
    unw_eth = deploy("UnwEth", chain)
    if exchange_address is not None:
        if exchange_address is not None:
            txid = unw_eth.transact(
                {"from": web3.eth.accounts[0]}).addAuthorizedAddress(exchange_address)
            check_successful_tx(web3, txid)
    return unw_eth


def deploy_network(chain, name, symbol, decimals, fee_divisor=100, exchange_address=None):
    web3 = chain.web3
    currency_network = deploy("CurrencyNetwork", chain)

    txid = currency_network.transact(
        {"from": web3.eth.accounts[0]}).init(name, symbol, decimals, fee_divisor)
    check_successful_tx(web3, txid)
    if exchange_address is not None:
        txid = currency_network.transact(
            {"from": web3.eth.accounts[0]}).addAuthorizedAddress(exchange_address)
        check_successful_tx(web3, txid)

    return currency_network


def deploy_proxied_network(chain, name, symbol, decimals, fee_divisor=100, exchange_address=None):
    web3 = chain.web3
    currency_network = deploy("CurrencyNetwork", chain)
    currency_network_address = currency_network.address
    print(currency_network_address)
    resolver = deploy("Resolver", chain, currency_network_address)
    proxy = deploy("EtherRouter", chain, resolver.address)
    print(proxy.address)
    proxied_trustlines = chain.provider.get_contract_factory("CurrencyNetwork")(proxy.address)
    txid = proxied_trustlines.transact().init(name, symbol, decimals, fee_divisor)
    check_successful_tx(web3, txid)
    if exchange_address is not None:
        txid = proxied_trustlines.transact().addAuthorizedAddress(exchange_address)
        check_successful_tx(web3, txid)

    txid = resolver.transact().registerLengthFunction("getUsers()",
                                                      "getUsersReturnSize()",
                                                      currency_network_address)
    check_successful_tx(web3, txid)
    txid = resolver.transact().registerLengthFunction("getFriends(address)",
                                                      "getFriendsReturnSize(address)",
                                                      currency_network_address)
    check_successful_tx(web3, txid)
    txid = resolver.transact().registerLengthFunction("getAccount(address,address)",
                                                      "getAccountLen()",
                                                      currency_network_address)
    check_successful_tx(web3, txid)
    txid = resolver.transact().registerLengthFunction("name()", "nameLen()",
                                                      currency_network_address)
    check_successful_tx(web3, txid)
    txid = resolver.transact().registerLengthFunction("symbol()", "symbolLen()",
                                                      currency_network_address)
    check_successful_tx(web3, txid)
    return proxied_trustlines


@contextmanager
def cd_into_projectpath():
    cwd = os.getcwd()
    install_filepath = os.path.join(sys.prefix, 'trustlines-contracts', 'project.json')

    if os.path.isfile(install_filepath):
        os.chdir(os.path.join(sys.prefix, 'trustlines-contracts'))
        yield
    else:
        raise RuntimeError('Projectfolder not found')
    os.chdir(cwd)


def deploy_networks(chain, networks):
    exchange = deploy_exchange(chain)
    unw_eth = deploy_unw_eth(chain, exchange.address)

    networks = [deploy_network(chain, name, symbol, decimals=decimals, exchange_address=exchange.address) for
                (name, symbol, decimals) in networks]

    return networks, exchange, unw_eth


def get_project():
    with cd_into_projectpath():
        return Project()
