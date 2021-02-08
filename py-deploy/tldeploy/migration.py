import collections
import math
import os
from typing import Dict, Set

import click
from deploy_tools.files import read_addresses_in_csv
from deploy_tools.transact import (
    send_function_call_transaction,
    increase_transaction_options_nonce,
    wait_for_successful_transaction_receipts,
)
from tldeploy.interests import balance_with_interests
from tldeploy.load_contracts import get_contract_interface


ADDRESS_0 = "0x0000000000000000000000000000000000000000"


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
        self.migrate_trustline_update_requests()
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

                # the value of is_frozen we get from `getAccount` on a frozen network is always true, so not correct.
                is_frozen = get_last_frozen_status_of_account(
                    self.old_network, user, friend
                )

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

    def migrate_trustline_update_requests(self):
        click.secho("Trustline requests migration")
        request_events = get_pending_trustline_update_requests(self.old_network)
        for request_event in request_events:
            event_args = request_event["args"]
            set_trustline_request_call = self.new_network.functions.setTrustlineRequest(
                event_args["_creditor"],
                event_args["_debtor"],
                event_args["_creditlineGiven"],
                event_args["_creditlineReceived"],
                event_args["_interestRateGiven"],
                event_args["_interestRateReceived"],
                event_args["_isFrozen"],
            )
            self.call_contract_function_with_tx(set_trustline_request_call)

        self.wait_for_successfull_txs_in_queue()
        click.secho("Trustline requests migration complete")

    def unfreeze_network(self):
        unfreeze_call = self.new_network.functions.unfreezeNetwork()
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


def get_last_frozen_status_of_account(currency_network, user, friend):
    """Return the last frozen status of a trustline
    The difference with the value returned by `contract.function.getAccount(user, friend).call()` is that the value
    will always be true for a frozen network via `getAccout` while `get_last_status_of_old_account` will give the
    value of the trustline before the network froze."""

    last_event = get_last_trustline_update_event(currency_network, user, friend)
    return last_event["args"]["_isFrozen"]


def get_last_trustline_update_event(currency_network, user, friend):
    trustline_updates_from_user = currency_network.events.TrustlineUpdate().getLogs(
        fromBlock=0, argument_filters={"_creditor": user, "_debtor": friend}
    )
    trustline_updates_from_friend = currency_network.events.TrustlineUpdate().getLogs(
        fromBlock=0, argument_filters={"_creditor": friend, "_debtor": user}
    )
    all_trustline_updates = trustline_updates_from_user + trustline_updates_from_friend
    sorted_trustline_updates = sorted_events(all_trustline_updates)

    assert (
        len(sorted_trustline_updates) >= 1
    ), f"Did not find any trustline update in between {user} and {friend}"

    return sorted_trustline_updates[len(sorted_trustline_updates) - 1]


def sorted_events(events, reverse=False):
    def log_index_key(event):
        if event.get("logIndex") is None:
            raise RuntimeError("No log index, events cannot be ordered truthfully.")
        return event.get("logIndex")

    def block_number_key(event):
        if event.get("blockNumber") is None:
            return math.inf
        return event.get("blockNumber")

    return sorted(
        events,
        key=lambda event: (block_number_key(event), log_index_key(event)),
        reverse=reverse,
    )


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


def get_pending_trustline_update_requests(currency_network):
    all_requests = currency_network.events.TrustlineUpdateRequest().getLogs(fromBlock=0)
    # we need to delete trustline requests that have been canceled
    all_cancel = currency_network.events.TrustlineUpdateCancel().getLogs(fromBlock=0)
    # we need to delete trustline requests that have been accepted and resulted in a trustline update
    all_updates = currency_network.events.TrustlineUpdate().getLogs(fromBlock=0)

    all_events = all_requests + all_cancel + all_updates
    all_events = sorted_events(all_events)

    latest_trustline_updates = dict()

    for event in all_events:
        if event.get("event") == "TrustlineUpdateRequest":
            uid = unique_id(event["args"]["_creditor"], event["args"]["_debtor"])
            latest_trustline_updates[uid] = event
        elif event.get("event") == "TrustlineUpdateCancel":
            uid = unique_id(event["args"]["_initiator"], event["args"]["_counterparty"])
            del latest_trustline_updates[uid]
        elif event.get("event") == "TrustlineUpdate":
            uid = unique_id(event["args"]["_creditor"], event["args"]["_debtor"])
            if uid in latest_trustline_updates.keys():
                del latest_trustline_updates[uid]
        else:
            raise RuntimeError(
                f"Expected event of type TrustlineUpdateRequest, TrustlineUpdateCancel, or TrustlineUpdate, "
                f"got: {event}"
            )

    return list(latest_trustline_updates.values())


def unique_id(user_1: str, user_2: str):
    if user_1 < user_2:
        return user_1 + user_2
    else:
        return user_2 + user_1
