#! pytest

import pytest

from tldeploy.core import deploy_network
from .conftest import EXPIRATION_TIME

"""
This file showcases how to get relevant information related to trustlines update
only using events (and events timestamps)
see https://github.com/trustlines-network/project/issues/545 for motive
"""

trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
]  # (A, B, clAB, clBA)

NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 100,
    "default_interest_rate": 1000,
    "custom_interests": False,
    "currency_network_contract_name": "TestCurrencyNetwork",
    "set_account_enabled": True,
    "expiration_time": EXPIRATION_TIME,
}


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(web3, accounts):
    contract = deploy_network(web3, **NETWORK_SETTING)
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccountDefaultInterests(
            accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0
        ).transact()
    return contract


@pytest.fixture()
def currency_network_with_pending_interests(
    web3, currency_network_contract_with_trustlines, accounts, chain
):
    """
    returns a currency network with updated balance accruing interests over one year
    the interests are not collected yet
    """
    for (A, B, clAB, clBA) in trustlines:
        currency_network_contract_with_trustlines.functions.transfer(
            accounts[B], 10, 0, [accounts[B]], b""
        ).transact({"from": accounts[A]})

    timestamp = web3.eth.getBlock("latest").timestamp
    timestamp += 3600 * 24 * 365

    chain.time_travel(timestamp)
    chain.mine_block()
    return currency_network_contract_with_trustlines


def calculate_interests(
    balance: int, delta_time_in_seconds: int, highest_order: int = 15
) -> int:
    """
    This function was taken from the relay server, for a proof of the correctness of this calculation see
    `relay/tests/unit/network_graph/test_interests.py`: test_interests_calculation_gives_same_result_as_smart_contracts
    """
    SECONDS_PER_YEAR = 60 * 60 * 24 * 365
    INTERESTS_DECIMALS = 2
    internal_interest_rate = 1000

    intermediate_order = balance
    interests = 0
    # Calculate compound interests using taylor approximation
    for order in range(1, highest_order + 1):
        intermediate_order = int(
            intermediate_order
            * internal_interest_rate
            * delta_time_in_seconds
            / (SECONDS_PER_YEAR * 100 * 10 ** INTERESTS_DECIMALS * order)
        )

        if intermediate_order == 0:
            break
        interests += intermediate_order

    return interests


def get_last_interest_update(web3, network, block_number, a, b):
    balance_update_events_from_a_to_b = network.events.BalanceUpdate.createFilter(
        fromBlock=0, toBlock=block_number, argument_filters={"_from": a, "_to": b}
    ).get_all_entries()

    # We want the second to last event to get the balance before interests are applied
    balance_update_events_from_a_to_b = sorted(
        balance_update_events_from_a_to_b, key=lambda x: x["blockNumber"], reverse=True
    )
    # TODO: Should consider log index in case there are multiple BalanceUpdate events for a and b in the block
    balance_before_interests_and_transfer = balance_update_events_from_a_to_b[1][
        "args"
    ]["_value"]

    # The timestamp is not actually in the event. We need to get it from elsewhere (ethindex db)
    timestamp_before_interest = web3.eth.getBlock(
        balance_update_events_from_a_to_b[1]["blockNumber"]
    )["timestamp"]
    timestamp_at_interest = web3.eth.getBlock(
        balance_update_events_from_a_to_b[0]["blockNumber"]
    )["timestamp"]
    delta_time = timestamp_at_interest - timestamp_before_interest

    interests = calculate_interests(balance_before_interests_and_transfer, delta_time)

    return interests


def test_on_sent_transfer_path_information(
    currency_network_contract_with_trustlines, accounts, web3
):
    """
    test that we can get the path of a sent transfer from the transfer event
    """
    network = currency_network_contract_with_trustlines
    initial_block_number = web3.eth.blockNumber

    path = [accounts[1], accounts[2], accounts[3]]
    network.functions.transfer(accounts[3], 75, 50, path, b"").transact(
        {"from": accounts[0]}
    )

    transfer_events = network.events.Transfer.createFilter(
        fromBlock=initial_block_number
    ).get_all_entries()

    transfer_event = transfer_events[0]
    transfer_event_log_index = transfer_event["logIndex"]
    transfer_block_number = transfer_event["blockNumber"]

    balance_update_events = network.events.BalanceUpdate.createFilter(
        fromBlock=transfer_block_number, toBlock=transfer_block_number
    ).get_all_entries()

    path_from_events = []
    reached_receiver_event = False
    for i in range(transfer_event_log_index - 1, -1, -1):
        for event in balance_update_events:
            if event["logIndex"] == i:
                path_from_events.append(event["args"]["_to"])
                if event["args"]["_to"] == accounts[3]:
                    reached_receiver_event = True
                break
        if reached_receiver_event:
            break

    print(path_from_events)
    assert path_from_events == path


def test_on_sent_transfer_value_paid_information_with_interests(
    currency_network_with_pending_interests, accounts, web3
):
    """
    Shows that we can get the information of what value I sent via a transfer from event (including fees)
    we assume we already know the path as it was demonstrated we can retrieve it

    This also shows we can find out the interests, since they are calculated as an intermediary
    This also shows we can find out the fees as they are `delta_balance - interests`
    """
    network = currency_network_with_pending_interests
    initial_block_number = web3.eth.blockNumber

    # the balance without interest in between account_0 and account_1
    initial_balance = network.functions.balance(accounts[0], accounts[1]).call()

    transfer_value = 75
    path = [accounts[1], accounts[2], accounts[3]]
    network.functions.transfer(accounts[3], transfer_value, 50, path, b"").transact(
        {"from": accounts[0]}
    )

    transfer_events = network.events.Transfer.createFilter(
        fromBlock=initial_block_number
    ).get_all_entries()

    transfer_event = transfer_events[0]
    transfer_event_log_index = transfer_event["logIndex"]
    transfer_block_number = transfer_event["blockNumber"]

    balance_update_events = network.events.BalanceUpdate.createFilter(
        fromBlock=transfer_block_number, toBlock=transfer_block_number
    ).get_all_entries()

    # We get the balance from the event that was emitted right before the Transfer event,
    # corresponding to the first TL in the path
    new_balance = 0
    for event in balance_update_events:
        if event["logIndex"] == transfer_event_log_index - 1:
            assert event["args"]["_from"] == accounts[0]
            assert event["args"]["_to"] == accounts[1]
            new_balance = event["args"]["_value"]
    assert new_balance == network.functions.balance(accounts[0], accounts[1]).call()

    # We have the new_balance, we need to calculate the interests in between the two last BalanceUpdate events
    interests = get_last_interest_update(
        web3, network, transfer_block_number, accounts[0], accounts[1]
    )
    delta_balance_due_to_transfer = new_balance - initial_balance - interests
    sent_value = -delta_balance_due_to_transfer
    # we should have sent 75 plus 2 fees in two intermediaries
    assert sent_value == transfer_value + 2

    # show we can also calculate the fees
    fees = sent_value - transfer_value
    assert fees == 2
