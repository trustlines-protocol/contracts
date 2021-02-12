# This file has been copied and adapted from the trustlines-contracts project.
# We like to get rid of the populus dependency and we don't want to compile the
# contracts when running tests in this project.
import json
from typing import Dict

import attr
import click
from deploy_tools import deploy_compiled_contract
from deploy_tools.transact import (
    increase_transaction_options_nonce,
    wait_for_successful_function_call,
)
from deploy_tools.files import read_addresses_in_csv
from tldeploy.migration import NetworkMigrater
from web3 import Web3
from tldeploy.load_contracts import contracts, get_contract_interface

from web3.contract import Contract


@attr.s
class NetworkSettings(object):
    name: str = attr.ib(default="Name")
    symbol: str = attr.ib(default="N")
    decimals: int = attr.ib(default=6)
    fee_divisor: int = attr.ib(default=0)
    default_interest_rate: int = attr.ib(default=0)
    custom_interests: bool = attr.ib(default=False)
    prevent_mediator_interests: bool = attr.ib(default=False)
    expiration_time: int = attr.ib(default=0)


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
        function_call = unw_eth.functions.addAuthorizedAddress(exchange_address)
        wait_for_successful_function_call(
            function_call,
            web3=web3,
            transaction_options=transaction_options,
            private_key=private_key,
        )
        increase_transaction_options_nonce(transaction_options)

    return unw_eth


def deploy_network(
    web3,
    network_settings: NetworkSettings,
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

    init_currency_network(
        web3=web3,
        network_settings=network_settings,
        currency_network=currency_network,
        exchange_address=exchange_address,
        authorized_addresses=authorized_addresses,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)

    return currency_network


def deploy_networks(
    web3,
    network_settings,
    currency_network_contract_name=None,
    transaction_options: Dict = None,
):
    exchange = deploy_exchange(web3=web3, transaction_options=transaction_options)
    unw_eth = deploy_unw_eth(
        web3=web3,
        exchange_address=exchange.address,
        transaction_options=transaction_options,
    )

    networks = [
        deploy_network(
            web3,
            exchange_address=exchange.address,
            currency_network_contract_name=currency_network_contract_name,
            transaction_options=transaction_options,
            network_settings=network_setting,
        )
        for network_setting in network_settings
    ]

    return networks, exchange, unw_eth


def deploy_identity(
    web3, owner_address, chain_id=None, transaction_options: Dict = None
):
    if transaction_options is None:
        transaction_options = {}
    identity = deploy("Identity", web3=web3, transaction_options=transaction_options)
    increase_transaction_options_nonce(transaction_options)
    if chain_id is None:
        chain_id = get_chain_id(web3)
    function_call = identity.functions.init(owner_address, chain_id)
    wait_for_successful_function_call(
        function_call, web3=web3, transaction_options=transaction_options
    )
    increase_transaction_options_nonce(transaction_options)

    return identity


def get_chain_id(web3):
    return int(web3.eth.chainId)


def deploy_beacon(
    web3,
    implementation_address,
    owner_address,
    *,
    private_key: bytes = None,
    transaction_options: Dict = None,
):
    if transaction_options is None:
        transaction_options = {}
    beacon = deploy(
        "ProxyBeacon",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
        constructor_args=(implementation_address,),
    )
    increase_transaction_options_nonce(transaction_options)
    if owner_address != beacon.functions.owner().call():
        transfer_ownership = beacon.functions.transferOwnership(owner_address)
        wait_for_successful_function_call(
            transfer_ownership,
            web3=web3,
            transaction_options=transaction_options,
            private_key=private_key,
        )
    return beacon


def deploy_currency_network_proxy(
    *,
    web3,
    network_settings: NetworkSettings,
    exchange_address=None,
    authorized_addresses=None,
    beacon_address,
    owner_address,
    private_key: bytes = None,
    transaction_options: Dict = None,
):
    verify_owner_not_deployer(web3, owner_address, private_key)

    if transaction_options is None:
        transaction_options = {}

    proxy = deploy(
        "AdministrativeProxy",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
        constructor_args=(beacon_address, ""),
    )
    increase_transaction_options_nonce(transaction_options)

    change_owner = proxy.functions.changeAdmin(owner_address)
    wait_for_successful_function_call(
        change_owner,
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)
    assert proxy.functions.admin().call({"from": owner_address}) == owner_address

    interface = get_contract_interface("CurrencyNetwork")
    proxied_currency_network = web3.eth.contract(
        abi=interface["abi"], address=proxy.address, bytecode=interface["bytecode"]
    )

    init_currency_network(
        web3=web3,
        network_settings=network_settings,
        currency_network=proxied_currency_network,
        exchange_address=exchange_address,
        authorized_addresses=authorized_addresses,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)

    return proxied_currency_network


def verify_owner_not_deployer(web3, owner_address, private_key):
    if private_key is not None:
        if owner_address == web3.eth.account.from_key(private_key=private_key).address:
            raise ValueError(
                "Private key address equals the proxy owner address. This prevents correct proxy initialization."
            )
    else:
        if owner_address == web3.eth.accounts[0]:
            raise ValueError(
                "Default node address equals the proxy owner address. This prevents correct proxy initialization."
            )


def init_currency_network(
    *,
    web3,
    currency_network,
    network_settings: NetworkSettings,
    exchange_address=None,
    authorized_addresses=None,
    transaction_options,
    private_key,
):
    if transaction_options is None:
        transaction_options = {}
    if authorized_addresses is None:
        authorized_addresses = []
    if exchange_address is not None:
        authorized_addresses.append(exchange_address)

    init_call = currency_network.functions.init(
        network_settings.name,
        network_settings.symbol,
        network_settings.decimals,
        network_settings.fee_divisor,
        network_settings.default_interest_rate,
        network_settings.custom_interests,
        network_settings.prevent_mediator_interests,
        network_settings.expiration_time,
        authorized_addresses,
    )

    wait_for_successful_function_call(
        init_call,
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )


def deploy_and_migrate_networks_from_file(
    *,
    web3,
    beacon_address: str,
    owner_address: str,
    addresses_file_path: str,
    private_key: bytes = None,
    transaction_options: Dict = None,
    output_file_path: str,
):
    """Deploy new owned currency network proxies and migrate old networks to it"""
    if transaction_options is None:
        transaction_options = {}

    verify_owner_not_deployer(web3, owner_address, private_key)
    currency_network_interface = get_contract_interface("CurrencyNetwork")
    network_addresses_mapping = {}

    for old_address in read_addresses_in_csv(addresses_file_path):
        old_network = web3.eth.contract(
            abi=currency_network_interface["abi"], address=old_address
        )
        new_network = deploy_and_migrate_network(
            web3=web3,
            beacon_address=beacon_address,
            owner_address=owner_address,
            old_network=old_network,
            private_key=private_key,
            transaction_options=transaction_options,
        )
        network_addresses_mapping[old_network.address] = new_network.address

    with open(output_file_path, "w") as file:
        json.dump(network_addresses_mapping, file)
        click.secho(
            "Wrote mapping {old_address: new_address} to " + output_file_path, fg="blue"
        )


def deploy_and_migrate_network(
    *,
    web3,
    beacon_address: str,
    owner_address: str,
    old_network: Contract,
    private_key: bytes = None,
    transaction_options: Dict = None,
):
    """Deploy a new owned currency network proxy and migrate the old networks to it"""
    if transaction_options is None:
        transaction_options = {}

    network_settings = get_network_settings(old_network)
    network_settings.expiration_time = 0

    new_network = deploy_currency_network_proxy(
        web3=web3,
        network_settings=network_settings,
        beacon_address=beacon_address,
        owner_address=owner_address,
        private_key=private_key,
        transaction_options=transaction_options,
    )
    new_address = new_network.address
    click.secho(
        message=f"Successfully deployed new proxy for currency network at {new_address}"
    )

    click.secho(f"Migrating {old_network.address} to {new_address}", fg="green")
    NetworkMigrater(
        web3, old_network.address, new_network.address, transaction_options, private_key
    ).migrate_network()
    click.secho(
        f"Migration of {old_network.address} to {new_address} complete", fg="green"
    )
    return new_network


def get_network_settings(currency_network):
    return NetworkSettings(
        name=currency_network.functions.name().call(),
        symbol=currency_network.functions.symbol().call(),
        decimals=currency_network.functions.decimals().call(),
        fee_divisor=currency_network.functions.capacityImbalanceFeeDivisor().call(),
        default_interest_rate=currency_network.functions.defaultInterestRate().call(),
        custom_interests=currency_network.functions.customInterests().call(),
        expiration_time=currency_network.functions.expirationTime().call(),
        prevent_mediator_interests=currency_network.functions.preventMediatorInterests().call(),
    )


class TransactionsFailed(Exception):
    def __init__(self, failed_tx_hashs):
        self.failed_tx_hashs = failed_tx_hashs
