import pytest

from tests.conftest import EXPIRATION_TIME
from tests.currency_network.conftest import deploy_test_network, NETWORK_SETTING

trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 0, 300, 300),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)


@pytest.fixture(scope="session")
def currency_network_contract_without_expiration(web3):
    return deploy_test_network(web3, {**NETWORK_SETTING, "expiration_time": 0})


@pytest.fixture(scope="session")
def currency_network_adapter_without_expiration(
    currency_network_contract_without_expiration, make_currency_network_adapter
):
    return make_currency_network_adapter(currency_network_contract_without_expiration)


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(
    web3, accounts, chain, make_currency_network_adapter
):
    contract = deploy_test_network(web3, NETWORK_SETTING)
    for (A, B, clAB, clBA) in trustlines:
        make_currency_network_adapter(contract).set_account(
            accounts[A], accounts[B], creditline_given=clAB, creditline_received=clBA
        )

    return contract


@pytest.fixture()
def frozen_currency_network_contract(currency_network_contract, chain):
    chain.time_travel(EXPIRATION_TIME)
    chain.mine_block()
    currency_network_contract.functions.freezeNetwork().transact()
    return currency_network_contract


@pytest.fixture()
def frozen_currency_network_adapter(
    frozen_currency_network_contract, make_currency_network_adapter
):
    return make_currency_network_adapter(frozen_currency_network_contract)


@pytest.fixture()
def currency_network_contract_with_frozen_trustline(
    currency_network_contract_with_trustlines, chain, accounts
):
    currency_network_contract_with_trustlines.functions.updateTrustline(
        accounts[0], 100, 150, 0, 0, True
    ).transact({"from": accounts[1]})
    currency_network_contract_with_trustlines.functions.updateTrustline(
        accounts[1], 150, 100, 0, 0, True
    ).transact({"from": accounts[0]})

    assert (
        currency_network_contract_with_trustlines.functions.isTrustlineFrozen(
            accounts[0], accounts[1]
        ).call()
        is True
    )
    return currency_network_contract_with_trustlines


@pytest.fixture()
def currency_network_adapter_with_frozen_trustline(
    currency_network_contract_with_frozen_trustline, make_currency_network_adapter
):
    return make_currency_network_adapter(
        currency_network_contract_with_frozen_trustline
    )


@pytest.fixture()
def frozen_currency_network_contract_with_trustlines(
    currency_network_contract_with_trustlines, chain
):
    chain.time_travel(EXPIRATION_TIME)
    chain.mine_block()
    currency_network_contract_with_trustlines.functions.freezeNetwork().transact()
    return currency_network_contract_with_trustlines


@pytest.fixture()
def frozen_currency_network_adapter_with_trustlines(
    frozen_currency_network_contract_with_trustlines, make_currency_network_adapter
):
    return make_currency_network_adapter(
        frozen_currency_network_contract_with_trustlines
    )


@pytest.fixture(scope="session")
def frozen_functions_and_args(accounts):
    """
    returns a list of functions that should fail when the network/trustline_0_1 is frozen and their arguments
    the functions are expected to be called from accounts[0]
    """
    return [
        ["transfer", (1, 2, [accounts[0], accounts[1]], b"")],
        ["transferReceiverPays", (1, 2, [accounts[0], accounts[1]], b"")],
        ["transferFrom", (1, 2, [accounts[0], accounts[1]], b"")],
        ["updateTrustline", (accounts[1], 101, 101, 101, 101, True)],
        ["updateCreditlimits", (accounts[1], 101, 101)],
        ["closeTrustline", [accounts[1]]],
        [
            "closeTrustlineByTriangularTransfer",
            (accounts[1], 100, [accounts[1], accounts[2]]),
        ],
    ]


def test_freeze_too_soon(currency_network_adapter):
    currency_network_adapter.freeze_network(should_fail=True)


def test_cannot_freeze_with_disabled_expiration(
    currency_network_adapter_without_expiration,
):
    assert currency_network_adapter_without_expiration.expiration_time == 0

    currency_network_adapter_without_expiration.freeze_network(should_fail=True)


def test_freeze(currency_network_contract, chain):
    assert currency_network_contract.functions.isNetworkFrozen().call() is False

    chain.time_travel(EXPIRATION_TIME)
    chain.mine_block()

    currency_network_contract.functions.freezeNetwork().transact()

    assert currency_network_contract.functions.isNetworkFrozen().call() is True


def test_trustline_frozen_if_network_frozen(
    frozen_currency_network_contract_with_trustlines, accounts
):
    assert (
        frozen_currency_network_contract_with_trustlines.functions.isTrustlineFrozen(
            accounts[0], accounts[1]
        ).call()
        is True
    )
    assert (
        frozen_currency_network_contract_with_trustlines.functions.getAccount(
            accounts[0], accounts[1]
        ).call()[4]
        is True
    )


def test_interaction_fails_if_network_frozen(
    frozen_currency_network_contract_with_trustlines,
    frozen_functions_and_args,
    accounts,
    assert_failing_transaction,
):
    network = frozen_currency_network_contract_with_trustlines

    # we need to authorize this address for testing transferFrom()
    network.functions.addAuthorizedAddress(accounts[0]).transact()

    for (function_name, arguments) in frozen_functions_and_args:
        assert_failing_transaction(
            getattr(network.functions, function_name)(*arguments), {"from": accounts[0]}
        )


def test_cannot_open_trustline_if_network_frozen(
    frozen_currency_network_adapter, accounts
):

    frozen_currency_network_adapter.update_trustline(
        accounts[0],
        accounts[1],
        creditline_given=101,
        creditline_received=101,
        is_frozen=True,
        should_fail=True,
    )


def test_freezing_trustline(currency_network_contract_with_trustlines, accounts):
    network = currency_network_contract_with_trustlines

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is False

    network.functions.updateTrustline(accounts[0], 100, 150, 0, 0, True).transact(
        {"from": accounts[1]}
    )
    network.functions.updateTrustline(accounts[1], 150, 100, 0, 0, True).transact(
        {"from": accounts[0]}
    )

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is True


def test_freezeing_trustline_requires_counter_party_agreement(
    currency_network_contract_with_trustlines, accounts
):
    network = currency_network_contract_with_trustlines

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is False

    network.functions.updateTrustline(accounts[0], 100, 150, 0, 0, True).transact(
        {"from": accounts[1]}
    )

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is False


def test_unfreezing_trustline(
    currency_network_contract_with_frozen_trustline, accounts
):

    network = currency_network_contract_with_frozen_trustline

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is True

    network.functions.updateTrustline(accounts[0], 100, 150, 0, 0, False).transact(
        {"from": accounts[1]}
    )
    network.functions.updateTrustline(accounts[1], 150, 100, 0, 0, False).transact(
        {"from": accounts[0]}
    )

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is False


def test_unfreezing_trustline_requires_counter_party_agreement(
    currency_network_contract_with_frozen_trustline, accounts
):

    network = currency_network_contract_with_frozen_trustline

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is True

    network.functions.updateTrustline(accounts[0], 100, 150, 0, 0, False).transact(
        {"from": accounts[1]}
    )

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is True


def test_cannot_unfreeze_trustline_if_network_frozen(
    frozen_currency_network_adapter_with_trustlines, accounts
):
    frozen_currency_network_adapter_with_trustlines.update_trustline(
        accounts[1],
        accounts[0],
        creditline_received=100,
        creditline_given=150,
        is_frozen=True,
        should_fail=True,
    )


def test_freezing_trustline_via_set_account(
    currency_network_contract_with_trustlines, accounts, make_currency_network_adapter
):
    network = currency_network_contract_with_trustlines
    A, B, *rest = accounts

    make_currency_network_adapter(network).set_account(A, B, is_frozen=True)

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is True


def test_freezing_trustline_via_set_account_default_interests(
    currency_network_contract_with_trustlines, accounts
):
    network = currency_network_contract_with_trustlines

    network.functions.setAccountDefaultInterests(
        accounts[0], accounts[1], 100, 100, True, 0, 12
    ).transact()

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is True


def test_updating_credit_limits_does_not_freeze(
    currency_network_contract_with_trustlines, accounts
):
    network = currency_network_contract_with_trustlines

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is False

    network.functions.updateCreditlimits(accounts[1], 10, 10).transact(
        {"from": accounts[0]}
    )

    assert network.functions.isTrustlineFrozen(accounts[0], accounts[1]).call() is False


def test_freezing_trustline_event(
    currency_network_contract_with_trustlines, web3, accounts
):
    network = currency_network_contract_with_trustlines

    initial_block = web3.eth.blockNumber

    network.functions.updateTrustline(accounts[0], 100, 150, 0, 0, True).transact(
        {"from": accounts[1]}
    )
    network.functions.updateTrustline(accounts[1], 150, 100, 0, 0, True).transact(
        {"from": accounts[0]}
    )

    trustline_update_request_event = network.events.TrustlineUpdateRequest.createFilter(
        fromBlock=initial_block
    ).get_all_entries()[0]
    trustline_update_event = network.events.TrustlineUpdate.createFilter(
        fromBlock=initial_block
    ).get_all_entries()[0]

    assert trustline_update_event["args"]["_debtor"] == accounts[0]
    assert trustline_update_event["args"]["_creditor"] == accounts[1]
    assert trustline_update_event["args"]["_isFrozen"] is True

    assert trustline_update_request_event["args"]["_debtor"] == accounts[0]
    assert trustline_update_request_event["args"]["_creditor"] == accounts[1]
    assert trustline_update_request_event["args"]["_isFrozen"] is True


def test_interaction_fails_if_trustline_frozen(
    currency_network_adapter_with_frozen_trustline,
    frozen_functions_and_args,
    accounts,
    assert_failing_transaction,
):
    # we need to authorize this address for testing transferFrom()
    currency_network_adapter_with_frozen_trustline.add_authorized_address(
        target=accounts[0], sender=accounts[0]
    )

    for (function_name, arguments) in frozen_functions_and_args:
        assert_failing_transaction(
            getattr(
                currency_network_adapter_with_frozen_trustline.contract.functions,
                function_name,
            )(*arguments),
            {"from": accounts[0]},
        )


def test_mediate_transfer_fails_if_intermediate_trustline_frozen(
    currency_network_adapter_with_frozen_trustline, accounts
):
    """
    The trustline in between 0 and 1 is frozen, tests that it cannot be used in a mediate transfer
    """
    path = [accounts[4], accounts[0], accounts[1], accounts[2]]

    currency_network_adapter_with_frozen_trustline.transfer(
        10, path=path, should_fail=True
    )
