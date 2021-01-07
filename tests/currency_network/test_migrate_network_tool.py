#! pytest

import pytest
from tldeploy.core import NetworkMigrater

from tests.conftest import CurrencyNetworkAdapter
from tests.currency_network.conftest import (
    trustlines,
    NETWORK_SETTING,
    NO_ONBOARDER,
    ADDRESS_0,
    deploy_ownable_network,
    deploy_test_network,
)


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def new_contract(web3, owner):
    settings = NETWORK_SETTING.copy()
    settings["transaction_options"] = {"from": owner}
    return deploy_ownable_network(web3, settings)


@pytest.fixture(scope="session")
def old_contract(
    web3, accounts, chain, on_boarders, on_boardees, creditors, debtors, debt_values
):
    """Create a currency network with on boardees, debts, and trustlines to migrate from"""

    settings = NETWORK_SETTING.copy()
    expiration_time = web3.eth.getBlock("latest")["timestamp"] + 1000
    settings["expiration_time"] = expiration_time
    contract = deploy_test_network(web3, settings)
    currency_network = CurrencyNetworkAdapter(contract)

    # set on boardees by opening trustlines from on boarder
    for (on_boarder, on_boardee) in zip(on_boarders, on_boardees):
        if on_boarder == NO_ONBOARDER:
            # NO_ONBOARDER is not really an account, and should (can) not send transactions
            # We use `set_account` to set NO_ONBOARDER to on_boardee
            currency_network.set_account(
                on_boarder, on_boardee, creditline_given=1, creditline_received=1
            )
        else:
            currency_network.update_trustline(
                on_boarder,
                on_boardee,
                creditline_given=1,
                creditline_received=1,
                accept=True,
            )
        assert (
            currency_network.get_on_boarder(on_boardee) == on_boarder
        ), "Setting up the on boarder failed"

    # set debts
    for (creditor, debtor, debt_value) in zip(creditors, debtors, debt_values):
        currency_network.increase_debt(debtor, creditor, debt_value)
        assert (
            currency_network.get_debt(debtor, creditor) == debt_value
        ), "Failed at setting up debts"

    # set trustlines
    for (A, B, clAB, clBA) in trustlines:
        CurrencyNetworkAdapter(contract).set_account(
            accounts[A], accounts[B], creditline_given=clAB, creditline_received=clBA
        )

    chain.time_travel(expiration_time)
    chain.mine_block()
    contract.functions.freezeNetwork().transact()
    return contract


@pytest.fixture(scope="session")
def assert_accounts_migrated(new_contract, accounts):
    def assert_migrated():
        for (first_user, second_user, credit_given, credit_received) in trustlines:
            (
                effective_credit_given,
                effective_credit_received,
                *rest,
            ) = new_contract.functions.getAccount(
                accounts[first_user], accounts[second_user]
            ).call()
            assert effective_credit_given == credit_given
            assert effective_credit_received == credit_received

    return assert_migrated


@pytest.fixture(scope="session")
def on_boarders(accounts):
    # The first on boarder is necessarily `NO_ONBOARDER`
    # Because two people without on boarders opening a trustline will not have on boarders.
    return [NO_ONBOARDER, accounts[0], accounts[1], accounts[2]]


@pytest.fixture(scope="session")
def on_boardees(accounts):
    return [accounts[0], accounts[1], accounts[2], accounts[3]]


@pytest.fixture(scope="session")
def assert_on_boarders_migrated(new_contract, on_boarders, on_boardees):
    def assert_migrated():
        for (on_boarder, on_boardee) in zip(on_boarders, on_boardees):
            assert new_contract.functions.onboarder(on_boardee).call() == on_boarder

    return assert_migrated


@pytest.fixture(scope="session")
def creditors(accounts):
    return [accounts[0], accounts[1], accounts[2]]


@pytest.fixture(scope="session")
def debtors(accounts):
    return [accounts[1], accounts[2], accounts[3]]


@pytest.fixture(scope="session")
def debt_values():
    return [123, 456, 789]


@pytest.fixture(scope="session")
def assert_debts_migrated(new_contract, creditors, debtors, debt_values):
    def assert_debt():
        for (creditor, debtor, debt_value) in zip(creditors, debtors, debt_values):
            assert (
                CurrencyNetworkAdapter(new_contract).get_debt(debtor, creditor)
                == debt_value
            )

    return assert_debt


@pytest.fixture()
def network_migrater(web3, new_contract, owner, old_contract):
    return NetworkMigrater(
        web3,
        old_contract.address,
        new_contract.address,
        transaction_options={"from": owner},
    )


def test_migrate_network_accounts(network_migrater, assert_accounts_migrated):
    network_migrater.migrate_accounts()
    assert_accounts_migrated()


def test_migrate_network_on_boarders(network_migrater, assert_on_boarders_migrated):
    network_migrater.migrate_on_boarders()
    assert_on_boarders_migrated()


def test_migrate_network_debts(network_migrater, assert_debts_migrated):
    network_migrater.migrate_debts()
    assert_debts_migrated()


def test_unfreeze_new_network(network_migrater, new_contract):
    network_migrater.unfreeze_network()
    assert new_contract.functions.isNetworkFrozen().call() is False


def test_remove_owner(network_migrater, new_contract):
    network_migrater.remove_owner()
    assert new_contract.functions.owner().call() == ADDRESS_0


def test_migrate_network_global(
    network_migrater,
    new_contract,
    assert_debts_migrated,
    assert_on_boarders_migrated,
    assert_accounts_migrated,
):
    """Test that calling `migrate_network` will migrate accounts, on boarders, debts,
       unfreeze the network and remove the owner"""
    network_migrater.migrate_network()

    assert_accounts_migrated()
    assert_on_boarders_migrated()
    assert_debts_migrated()
    assert new_contract.functions.isNetworkFrozen().call() is False
    assert new_contract.functions.owner().call() == ADDRESS_0
