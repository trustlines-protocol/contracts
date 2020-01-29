# This file has been copied and adapted from the trustlines-contracts project.
# We like to get rid of the populus dependency and we don't want to compile the
# contracts when running tests in this project.

import collections
import json
import os
import sys
from typing import Dict

from deploy_tools import deploy_compiled_contract
from deploy_tools.deploy import (
    increase_transaction_options_nonce,
    send_function_call_transaction,
)
from web3 import Web3


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


def get_contract_interface(contract_name):
    return contracts[contract_name]


def deploy(
    contract_name,
    *,
    web3: Web3,
    transaction_options: Dict = None,
    private_key: bytes = None,
    constructor_args=(),
):
    if transaction_options is None:
        transaction_options = {}

    contract_interface = contracts[contract_name]
    return deploy_compiled_contract(
        abi=contract_interface["abi"],
        bytecode=contract_interface["bytecode"],
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
        constructor_args=constructor_args,
    )


def deploy_exchange(
    *, web3: Web3, transaction_options: Dict = None, private_key: bytes = None
):
    if transaction_options is None:
        transaction_options = {}

    exchange = deploy(
        "Exchange",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)
    return exchange


def deploy_unw_eth(
    *,
    web3: Web3,
    transaction_options: Dict = None,
    private_key: bytes = None,
    exchange_address=None,
):
    if transaction_options is None:
        transaction_options = {}

    unw_eth = deploy(
        "UnwEth",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )

    increase_transaction_options_nonce(transaction_options)

    if exchange_address is not None:
        if exchange_address is not None:
            function_call = unw_eth.functions.addAuthorizedAddress(exchange_address)
            send_function_call_transaction(
                function_call,
                web3=web3,
                transaction_options=transaction_options,
                private_key=private_key,
            )
            increase_transaction_options_nonce(transaction_options)

    return unw_eth


def deploy_network(
    web3,
    name,
    symbol,
    decimals,
    expiration_time,
    fee_divisor=0,
    default_interest_rate=0,
    custom_interests=True,
    prevent_mediator_interests=False,
    exchange_address=None,
    currency_network_contract_name=None,
    transaction_options: Dict = None,
    private_key=None,
    authorized_addresses=None,
):
    if transaction_options is None:
        transaction_options = {}
    if authorized_addresses is None:
        authorized_addresses = []

    # CurrencyNetwork is the standard contract to deploy, If we're running
    # tests or trying to export data for testing the python implementation of
    # private functions, we may want deploy the TestCurrencyNetwork contract
    # instead.
    if currency_network_contract_name is None:
        currency_network_contract_name = "CurrencyNetwork"

    currency_network = deploy(
        currency_network_contract_name,
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)

    if exchange_address is not None:
        authorized_addresses.append(exchange_address)

    init_function_call = currency_network.functions.init(
        name,
        symbol,
        decimals,
        fee_divisor,
        default_interest_rate,
        custom_interests,
        prevent_mediator_interests,
        expiration_time,
        authorized_addresses,
    )

    send_function_call_transaction(
        init_function_call,
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)

    return currency_network


def deploy_networks(web3, network_settings, currency_network_contract_name=None):
    exchange = deploy_exchange(web3=web3)
    unw_eth = deploy_unw_eth(web3=web3, exchange_address=exchange.address)

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


def deploy_identity(web3, owner_address, chain_id=None):
    identity = deploy("Identity", web3=web3)

    if chain_id is None:
        chain_id = get_chain_id(web3)
    function_call = identity.functions.init(owner_address, chain_id)
    send_function_call_transaction(function_call, web3=web3)

    return identity


def get_chain_id(web3):
    return int(web3.eth.chainId)
