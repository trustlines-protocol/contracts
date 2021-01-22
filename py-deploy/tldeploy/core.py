# This file has been copied and adapted from the trustlines-contracts project.
# We like to get rid of the populus dependency and we don't want to compile the
# contracts when running tests in this project.

import collections
import os
from typing import Dict, Set

import attr
import click
from deploy_tools import deploy_compiled_contract
from deploy_tools.transact import (
    increase_transaction_options_nonce,
    send_function_call_transaction,
    wait_for_successful_function_call,
    wait_for_successful_transaction_receipts,
)
from deploy_tools.files import read_addresses_in_csv
from tldeploy.interests import balance_with_interests
from web3 import Web3
from tlbin import load_packaged_contracts
from web3.contract import Contract

ADDRESS_0 = "0x0000000000000000000000000000000000000000"


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


# lazily load the contracts, so the compile_contracts fixture has a chance to
# set TRUSTLINES_CONTRACTS_JSON
class LazyContractsLoader(collections.UserDict):
    def __getitem__(self, *args):
        if not self.data:
            self.data = load_packaged_contracts()
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
    exchange = deploy_exchange(web3=web3)
    unw_eth = deploy_unw_eth(web3=web3, exchange_address=exchange.address)

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
):
    """Deploy new owned currency network proxies and migrate old networks to it"""
    if transaction_options is None:
        transaction_options = {}

    verify_owner_not_deployer(web3, owner_address, private_key)
    currency_network_interface = get_contract_interface("CurrencyNetwork")

    for old_address in read_addresses_in_csv(addresses_file_path):
        old_network = web3.eth.contract(
            abi=currency_network_interface["abi"], address=old_address
        )
        deploy_and_migrate_network(
            web3=web3,
            beacon_address=beacon_address,
            owner_address=owner_address,
            old_network=old_network,
            private_key=private_key,
            transaction_options=transaction_options,
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


def migrate_networks(
    web3,
    old_addresses_file_path: str,
    new_addresses_file_path: str,
    transaction_options: Dict = None,
    private_key: bytes = None,
):
    for [old_address, new_address] in read_addresses_to_migrate(
        old_addresses_file_path, new_addresses_file_path
    ):
        click.secho(f"Migrating {old_address} to {new_address}", fg="green")
        NetworkMigrater(
            web3, old_address, new_address, transaction_options, private_key
        ).migrate_network()
        click.secho(f"Migration of {old_address} to {new_address} complete", fg="green")


def verify_networks_migrations(
    web3, old_addresses_file_path: str, new_addresses_file_path: str
):

    for [old_address, new_address] in read_addresses_to_migrate(
        old_addresses_file_path, new_addresses_file_path
    ):
        click.secho(
            f"Verifying migration from {old_address} to {new_address}", fg="green"
        )
        NetworkMigrationVerifier(web3, old_address, new_address).verify_migration()
        click.secho(
            f"Verification of migration from {old_address} to {new_address} complete",
            fg="green",
        )


def read_addresses_to_migrate(old_addresses_file_path, new_addresses_file_path):
    if not os.path.isfile(old_addresses_file_path):
        raise ValueError(f"Old addresses file not found at {old_addresses_file_path}")
    if not os.path.isfile(new_addresses_file_path):
        raise ValueError(f"New addresses file not found at {new_addresses_file_path}")

    old_currency_network_addresses = read_addresses_in_csv(old_addresses_file_path)
    new_currency_network_addresses = read_addresses_in_csv(new_addresses_file_path)

    if len(old_currency_network_addresses) != len(new_currency_network_addresses):
        raise ValueError(
            f"The number of old and new addresses do not match: "
            f"{len(old_currency_network_addresses)} old and {len(new_currency_network_addresses)} new"
        )

    return zip(old_currency_network_addresses, new_currency_network_addresses)


class NetworkMigrationVerifier:
    def __init__(
        self, web3, old_currency_network_address: str, new_currency_network_address: str
    ):
        old_network_interface = get_contract_interface("CurrencyNetwork")
        self.old_network = web3.eth.contract(
            address=old_currency_network_address, abi=old_network_interface["abi"]
        )
        new_network_interface = get_contract_interface("CurrencyNetworkOwnable")
        self.new_network = web3.eth.contract(
            address=new_currency_network_address, abi=new_network_interface["abi"]
        )
        self.users = set(self.old_network.functions.getUsers().call())
        click.secho(
            f"Found {len(self.users)} users in the old currency network", fg="blue"
        )

    def verify_migration(self):
        assert (
            self.old_network.functions.isNetworkFrozen().call()
        ), "Old contract not frozen"
        assert (
            self.old_network.functions.name().call()
            == self.new_network.functions.name().call()
        ), "New and old contracts name do not match"

        self.verify_accounts_migrated()
        self.verify_on_boarders_migrated()
        self.verify_debts_migrated()
        self.verify_network_unfrozen()
        self.verify_owner_removed()

    def verify_accounts_migrated(self):
        for user in self.users:
            friends = set(self.old_network.functions.getFriends(user).call())
            for friend in friends:
                if not self.is_account_migrated(user, friend):
                    self.warn_account_verification_failed(user, friend)
        click.secho("Accounts migration verified")

    def is_account_migrated(self, user, friend):
        (
            old_credit_given,
            old_credit_received,
            old_interest_given,
            old_interest_received,
            old_is_frozen,
            old_mtime,
            old_balance,
        ) = self.old_network.functions.getAccount(user, friend).call()
        (
            new_credit_given,
            new_credit_received,
            new_interest_given,
            new_interest_received,
            new_is_frozen,
            new_mtime,
            new_balance,
        ) = self.new_network.functions.getAccount(user, friend).call()

        if new_mtime < old_mtime:
            # The account was not migrated at all or modified on old network after migration
            return False

        old_balance_with_interests = balance_with_interests(
            old_balance,
            old_interest_given,
            old_interest_received,
            new_mtime - old_mtime,
        )

        # We do not verify is_frozen because old network was necessarily frozen and new network will not be
        if (
            old_credit_given,
            old_credit_received,
            old_interest_given,
            old_interest_received,
        ) != (
            new_credit_given,
            new_credit_received,
            new_interest_given,
            new_interest_received,
        ) or old_balance_with_interests != new_balance:
            return False
        return True

    def warn_account_verification_failed(self, user, friend):
        click.secho(f"Account verification failed for {user} - {friend}", fg="red")

    def verify_on_boarders_migrated(self):
        for user in self.users:
            if not self.is_on_boarder_migrated(user):
                click.secho(f"On boarder verification failed for {user}", fg="red")
        click.secho("On boarder migration verified")

    def is_on_boarder_migrated(self, user):
        old_on_boarder = self.old_network.functions.onboarder(user).call()
        new_on_boarder = self.new_network.functions.onboarder(user).call()
        return old_on_boarder == new_on_boarder

    def verify_debts_migrated(self):
        debts = get_all_debts_of_currency_network(self.old_network)
        for debtor in debts.keys():
            for creditor in debts[debtor].keys():
                if not self.is_debt_migrated(debts, debtor, creditor):
                    click.secho(
                        f"Debt verification failed for debtor {debtor} to creditor {creditor}",
                        fg="red",
                    )
        click.secho("Debts migration verified")

    def is_debt_migrated(self, debts, debtor, creditor):
        old_debt = debts[debtor][creditor]
        new_debt = self.new_network.functions.getDebt(debtor, creditor).call()
        return old_debt == new_debt

    def verify_network_unfrozen(self):
        if self.new_network.functions.isNetworkFrozen().call():
            click.secho("New network is still frozen", fg="red")
        else:
            click.secho("New network is unfrozen")

    def verify_owner_removed(self):
        new_owner = self.new_network.functions.owner().call()
        if new_owner != ADDRESS_0:
            click.secho(f"New network owner is not zero address {new_owner}", fg="red")
        else:
            click.secho("New network owner is zero address")


class NetworkMigrater(NetworkMigrationVerifier):
    def __init__(
        self,
        web3,
        old_currency_network_address: str,
        new_currency_network_address: str,
        transaction_options: Dict = None,
        private_key: bytes = None,
        max_tx_queue_size=10,
    ):
        super().__init__(
            web3, old_currency_network_address, new_currency_network_address
        )

        self.web3 = web3
        if private_key is not None:
            self.web3.eth.defaultAccount = web3.eth.account.from_key(
                private_key=private_key
            ).address

        self.transaction_options = transaction_options
        if transaction_options is None:
            self.transaction_options = {}

        self.private_key = private_key
        self.max_tx_queue_size = max_tx_queue_size
        self.tx_queue: Set[str] = set()

    def migrate_network(self):
        assert (
            self.new_network.functions.isNetworkFrozen().call()
        ), "New contract not frozen"
        assert (
            self.old_network.functions.name().call()
            == self.new_network.functions.name().call()
        ), "New and old contracts name do not match"

        self.freeze_old_network()
        self.migrate_accounts()
        self.migrate_on_boarders()
        self.migrate_debts()
        self.unfreeze_network()
        self.remove_owner()

    def freeze_old_network(self):
        if not self.old_network.functions.isNetworkFrozen().call():
            freeze_network_call = self.old_network.functions.freezeNetwork()
            self.call_contract_function_with_tx(freeze_network_call)
            self.wait_for_successfull_txs_in_queue()

    def migrate_accounts(self):
        click.secho("Accounts migration")
        for user in self.users:
            friends = set(self.old_network.functions.getFriends(user).call())
            for friend in friends:
                if user < friend:
                    # For each (user, friend) pair we only need to migrate the account once
                    # We arbitrarily decide not to migrate in the case user < friend
                    continue
                if self.is_account_migrated(user, friend):
                    continue
                (
                    creditline_ab,
                    creditline_ba,
                    interest_ab,
                    interest_ba,
                    is_frozen,
                    mtime,
                    balance_ab,
                ) = self.old_network.functions.getAccount(user, friend).call()
                set_account_call = self.new_network.functions.setAccount(
                    user,
                    friend,
                    creditline_ab,
                    creditline_ba,
                    interest_ab,
                    interest_ba,
                    is_frozen,
                    mtime,
                    balance_ab,
                )
                self.call_contract_function_with_tx(set_account_call)
        self.wait_for_successfull_txs_in_queue()
        click.secho("Accounts migration complete")

    def migrate_on_boarders(self):
        click.secho("On boarders migration")
        for user in self.users:
            if not self.is_on_boarder_migrated(user):
                on_boarder = self.old_network.functions.onboarder(user).call()
                set_on_boarder_call = self.new_network.functions.setOnboarder(
                    user, on_boarder
                )
                self.call_contract_function_with_tx(set_on_boarder_call)
        self.wait_for_successfull_txs_in_queue()
        click.secho("On boarders migration complete")

    def migrate_debts(self):
        click.secho("Debts migration")
        debts = get_all_debts_of_currency_network(self.old_network)
        for debtor in debts.keys():
            for creditor in debts[debtor].keys():
                set_debt_call = self.new_network.functions.setDebt(
                    debtor, creditor, debts[debtor][creditor]
                )
                self.call_contract_function_with_tx(set_debt_call)
        self.wait_for_successfull_txs_in_queue()
        click.secho("Debts migration complete")

    def unfreeze_network(self):
        unfreeze_call = self.new_network.functions.unFreezeNetwork()
        self.call_contract_function_with_tx(unfreeze_call)
        self.wait_for_successfull_txs_in_queue()

    def remove_owner(self):
        remove_owner_call = self.new_network.functions.removeOwner()
        self.call_contract_function_with_tx(remove_owner_call)
        self.wait_for_successfull_txs_in_queue()

    def call_contract_function_with_tx(self, function_call):
        tx_hash = send_function_call_transaction(
            function_call,
            web3=self.web3,
            transaction_options=self.transaction_options,
            private_key=self.private_key,
        )
        increase_transaction_options_nonce(self.transaction_options)
        self.tx_queue.add(tx_hash)

        if len(self.tx_queue) >= self.max_tx_queue_size:
            self.wait_for_successfull_txs_in_queue()

    def wait_for_successfull_txs_in_queue(self):
        wait_for_successful_transaction_receipts(self.web3, self.tx_queue)
        self.tx_queue = set()


def get_all_debts_of_currency_network(currency_network):
    # We have to use events to retrieve the debts
    # We cannot use `users` of the currency network as some non users could have set a debt
    all_debt_updates = currency_network.events.DebtUpdate().getLogs(fromBlock=0)
    debts = collections.defaultdict(lambda: {})

    for debt_update in all_debt_updates:
        creditor = debt_update["args"]["_creditor"]
        debtor = debt_update["args"]["_debtor"]
        value = debt_update["args"]["_newDebt"]

        if creditor < debtor:
            debts[debtor][creditor] = value
        else:
            debts[creditor][debtor] = -value

    return debts


class TransactionsFailed(Exception):
    def __init__(self, failed_tx_hashs):
        self.failed_tx_hashs = failed_tx_hashs
