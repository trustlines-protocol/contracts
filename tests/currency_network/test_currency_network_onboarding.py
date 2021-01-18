from tests.currency_network.conftest import ADDRESS_0, NO_ONBOARDER


def open_trustline(network, a, b):
    network.functions.updateCreditlimits(b, 1, 1).transact({"from": a})
    network.functions.updateCreditlimits(a, 1, 1).transact({"from": b})


def test_no_onboarder(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])

    assert (
        currency_network_contract.functions.onboarder(accounts[1]).call()
        == NO_ONBOARDER
    )
    assert (
        currency_network_contract.functions.onboarder(accounts[2]).call()
        == NO_ONBOARDER
    )


def test_onboarder_simple_trustline(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])
    open_trustline(currency_network_contract, accounts[2], accounts[3])

    assert (
        currency_network_contract.functions.onboarder(accounts[3]).call() == accounts[2]
    )


def test_cannot_change_no_onboarder(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])
    assert (
        currency_network_contract.functions.onboarder(accounts[2]).call()
        == NO_ONBOARDER
    )

    open_trustline(currency_network_contract, accounts[2], accounts[3])
    assert (
        currency_network_contract.functions.onboarder(accounts[2]).call()
        == NO_ONBOARDER
    )


def test_cannot_change_onboarder(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])
    open_trustline(currency_network_contract, accounts[2], accounts[3])
    assert (
        currency_network_contract.functions.onboarder(accounts[3]).call() == accounts[2]
    )

    open_trustline(currency_network_contract, accounts[3], accounts[4])
    assert (
        currency_network_contract.functions.onboarder(accounts[3]).call() == accounts[2]
    )


def test_set_account_onboards(currency_network_contract, accounts):
    currency_network_contract.functions.setAccountDefaultInterests(
        accounts[1], accounts[2], 1, 1, False, 1, 1
    ).transact()

    assert (
        currency_network_contract.functions.onboarder(accounts[1]).call()
        == NO_ONBOARDER
    )
    assert (
        currency_network_contract.functions.onboarder(accounts[2]).call()
        == NO_ONBOARDER
    )


def test_onboarding_event_no_onboarder(currency_network_contract, web3, accounts):
    intial_block = web3.eth.blockNumber

    open_trustline(currency_network_contract, accounts[1], accounts[2])

    all_events = currency_network_contract.events.Onboard.createFilter(
        fromBlock=intial_block
    ).get_all_entries()
    event_onboarding_1 = currency_network_contract.events.Onboard.createFilter(
        fromBlock=intial_block, argument_filters={"_onboardee": accounts[1]}
    ).get_all_entries()

    assert len(all_events) == 2
    assert event_onboarding_1[0]["args"]["_onboarder"] == NO_ONBOARDER


def test_onboarding_event_with_onboarder(currency_network_contract, web3, accounts):
    intial_block = web3.eth.blockNumber

    open_trustline(currency_network_contract, accounts[1], accounts[2])
    open_trustline(currency_network_contract, accounts[2], accounts[3])

    all_events = currency_network_contract.events.Onboard.createFilter(
        fromBlock=intial_block
    ).get_all_entries()
    event_onboarding_3 = currency_network_contract.events.Onboard.createFilter(
        fromBlock=intial_block, argument_filters={"_onboardee": accounts[3]}
    ).get_all_entries()

    assert len(all_events) == 3
    assert event_onboarding_3[0]["args"]["_onboarder"] == accounts[2]


def test_onboarding_no_accept_tl(
    currency_network_contract, accounts, assert_failing_transaction
):
    """Test that users cannot attempt to open a TL with (0, 0, 0, 0) to onboard someone"""
    open_trustline(currency_network_contract, accounts[1], accounts[2])

    assert_failing_transaction(
        currency_network_contract.functions.updateCreditlimits(accounts[3], 0, 0),
        {"from": accounts[1]},
    )

    assert (
        currency_network_contract.functions.onboarder(accounts[3]).call() == ADDRESS_0
    )
