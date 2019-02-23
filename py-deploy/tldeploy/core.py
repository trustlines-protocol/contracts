# This file has been copied and adapted from the trustlines-contracts project.
# We like to get rid of the populus dependency and we don't want to compile the
# contracts when running tests in this project.

import os
import sys
import json
import collections

from deploy_tools import deploy_compiled_contract
from deploy_tools.deploy import wait_for_successful_transaction_receipt


def load_contracts_json():
    path = os.environ.get("TRUSTLINES_CONTRACTS_JSON") or os.path.join(
        sys.prefix, "trustlines-contracts", "build", "contracts.json"
    )
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


def deploy(contract_name, web3, *args):
    contract_interface = contracts[contract_name]
    return deploy_compiled_contract(
        abi=contract_interface["abi"],
        bytecode=contract_interface["bytecode"],
        web3=web3,
        constructor_args=args,
    )


def deploy_exchange(web3):
    exchange = deploy("Exchange", web3)
    return exchange


def deploy_unw_eth(web3, exchange_address=None):
    unw_eth = deploy("UnwEth", web3)
    if exchange_address is not None:
        if exchange_address is not None:
            txid = unw_eth.functions.addAuthorizedAddress(exchange_address).transact(
                {"from": web3.eth.accounts[0]}
            )
            wait_for_successful_transaction_receipt(web3, txid)
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
    currency_network_contract_name=None,
):
    # CurrencyNetwork is the standard contract to deploy, If we're running
    # tests or trying to export data for testing the python implementation of
    # private functions, we may want deploy the TestCurrencyNetwork contract
    # instead.
    if currency_network_contract_name is None:
        currency_network_contract_name = "CurrencyNetwork"
    currency_network = deploy(currency_network_contract_name, web3)

    txid = currency_network.functions.init(
        name,
        symbol,
        decimals,
        fee_divisor,
        default_interest_rate,
        custom_interests,
        prevent_mediator_interests,
    ).transact({"from": web3.eth.accounts[0]})
    wait_for_successful_transaction_receipt(web3, txid)
    if exchange_address is not None:
        txid = currency_network.functions.addAuthorizedAddress(
            exchange_address
        ).transact({"from": web3.eth.accounts[0]})
        wait_for_successful_transaction_receipt(web3, txid)

    return currency_network


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


def deploy_identity(web3, owner_address):
    identity = deploy("Identity", web3=web3)

    tx_id = identity.functions.init(owner_address).transact(
        {"from": web3.eth.accounts[0]}
    )
    wait_for_successful_transaction_receipt(web3, tx_id)

    return identity
