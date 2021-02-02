#! pytest

import pytest
from tldeploy.core import (
    NetworkSettings,
)
from tldeploy.migration import NetworkMigrater, get_last_frozen_status_of_account

from tests.currency_network.conftest import (
    NO_ONBOARDER,
    ADDRESS_0,
    deploy_ownable_network,
    deploy_test_network,
)

trustlines = [
    (0, 1, 100, 150, False),
    (1, 2, 200, 250, False),
    (3, 2, 300, 350, False),
    (4, 3, 400, 450, True),
    (0, 4, 500, 550, True),
]  # (A, B, clAB, clBA, is_frozen)

pending_trustlines_requests = [
    (0, 1, 1000, 1500, 1, 2, False),
    (1, 2, 2000, 2500, 4, 3, False),
    (3, 2, 3000, 3500, 5, 6, False),
    (4, 3, 4000, 4500, 4, 2, False),
    (0, 4, 5000, 5500, 1, 0, False),
]  # (A, B, clAB, clBA, interestAB, interestBA, is_frozen)


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def new_contract(web3, owner):
    return deploy_ownable_network(
        web3,
        NetworkSettings(custom_interests=True),
        transaction_options={"from": owner},
    )


@pytest.fixture(scope="session")
def old_contract(
    web3,
    accounts,
    chain,
    on_boarders,
    on_boardees,
    creditors,
    debtors,
    debt_values,
    make_currency_network_adapter,
):
    """Create a currency network with on boardees, debts, and trustlines to migrate from"""

    expiration_time = web3.eth.getBlock("latest")["timestamp"] + 1000
    settings = NetworkSettings(expiration_time=expiration_time, custom_interests=True)
    contract = deploy_test_network(web3, settings)
    currency_network = make_currency_network_adapter(contract)

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
    for (A, B, clAB, clBA, is_frozen) in trustlines:
        currency_network.update_trustline(
            accounts[A],
            accounts[B],
            creditline_given=clAB,
            creditline_received=clBA,
            is_frozen=is_frozen,
            accept=True,
        )

    # set pending trustline requests
    for (
        A,
        B,
        clAB,
        clBA,
        interest_AB,
        interest_BA,
        is_frozen,
    ) in pending_trustlines_requests:
        currency_network.update_trustline(
            accounts[A],
            accounts[B],
            creditline_given=clAB,
            creditline_received=clBA,
            interest_rate_given=interest_AB,
            interest_rate_received=interest_BA,
            is_frozen=is_frozen,
            accept=False,
        )

    chain.time_travel(expiration_time)
    chain.mine_block()
    contract.functions.freezeNetwork().transact()
    return contract


@pytest.fixture(scope="session")
def old_contract_adapter(old_contract, make_currency_network_adapter):
    return make_currency_network_adapter(old_contract)


@pytest.fixture(scope="session")
def new_contract_adapter(new_contract, make_currency_network_adapter):
    return make_currency_network_adapter(new_contract)


@pytest.fixture(scope="session")
def assert_accounts_migrated(new_contract, accounts):
    def assert_migrated():
        for (
            first_user,
            second_user,
            credit_given,
            credit_received,
            is_frozen,
        ) in trustlines:
            (
                effective_credit_given,
                effective_credit_received,
                effective_interest_given,
                effective_interest_received,
                effective_is_frozen,
                *rest,
            ) = new_contract.functions.getAccount(
                accounts[first_user], accounts[second_user]
            ).call()
            assert effective_credit_given == credit_given
            assert effective_credit_received == credit_received
            assert effective_is_frozen == is_frozen

    return assert_migrated


@pytest.fixture(scope="session")
def assert_pending_trusltines_migrated(new_contract_adapter, accounts):
    def assert_migrated():
        # test that the pending trustline updates were properly migrated by accepting them
        assert (
            new_contract_adapter.is_network_frozen() is False
        ), "Cannot test out the trustlines migration if network is still frozen"

        for (
            A,
            B,
            clAB,
            clBA,
            interest_AB,
            interest_BA,
            is_frozen,
        ) in pending_trustlines_requests:
            new_contract_adapter.update_trustline(
                accounts[B],
                accounts[A],
                creditline_given=clBA,
                creditline_received=clAB,
                interest_rate_given=interest_BA,
                interest_rate_received=interest_AB,
                is_frozen=is_frozen,
            )
            assert new_contract_adapter.check_account(
                accounts[A],
                accounts[B],
                clAB,
                clBA,
                interest_AB,
                interest_BA,
                is_frozen,
            )

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
def assert_debts_migrated(
    new_contract, creditors, debtors, debt_values, make_currency_network_adapter
):
    def assert_debt():
        for (creditor, debtor, debt_value) in zip(creditors, debtors, debt_values):
            assert (
                make_currency_network_adapter(new_contract).get_debt(debtor, creditor)
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
    # we want to unfreeze_network to truthfully test the `isFrozen` status of trustlines
    network_migrater.unfreeze_network()
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
    assert_pending_trusltines_migrated,
):
    """Test that calling `migrate_network` will migrate accounts, on boarders, debts,
    unfreeze the network and remove the owner"""
    network_migrater.migrate_network()

    assert_accounts_migrated()
    assert_on_boarders_migrated()
    assert_debts_migrated()
    assert_pending_trusltines_migrated()
    assert new_contract.functions.isNetworkFrozen().call() is False
    assert new_contract.functions.owner().call() == ADDRESS_0


def test_get_last_frozen_status_of_account(old_contract_adapter, accounts):
    old_contract_adapter.freeze_network_if_not_frozen()
    for (
        first_user,
        second_user,
        credit_given,
        credit_received,
        is_frozen,
    ) in trustlines:
        assert (
            get_last_frozen_status_of_account(
                old_contract_adapter.contract,
                accounts[first_user],
                accounts[second_user],
            )
            == is_frozen
        )
        assert (
            get_last_frozen_status_of_account(
                old_contract_adapter.contract,
                accounts[second_user],
                accounts[first_user],
            )
            == is_frozen
        )


def test_get_pending_trustline_requests(
    network_migrater, assert_pending_trusltines_migrated
):
    network_migrater.migrate_trustline_update_requests()
    network_migrater.unfreeze_network()
    assert_pending_trusltines_migrated()
