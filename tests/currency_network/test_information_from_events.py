#! pytest

import pytest

from tests.conftest import EXPIRATION_TIME
from tests.currency_network.conftest import deploy_test_network

"""
This file showcases how to get relevant information related to trustlines transfer
only using events (and events timestamps)
see https://github.com/trustlines-network/project/issues/545 for motive
These tests shall ensure that the information stays available, but also work as an example of how to implement it.
Of course there might be optimizations possible in the specific case.
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
    "expiration_time": EXPIRATION_TIME,
    "prevent_mediator_interests": False,
}


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(web3, accounts):
    contract = deploy_test_network(web3, NETWORK_SETTING)
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccountDefaultInterests(
            accounts[A], accounts[B], clAB, clBA, False, 0, 0
        ).transact()
    return contract


@pytest.fixture()
def currency_network_with_pending_interests(
    web3, currency_network_contract_with_trustlines, accounts, chain
):
    """
    returns a currency network with updated balance accruing interests over one year
    the interests are not collected yet.
    """
    for (A, B, clAB, clBA) in trustlines:
        currency_network_contract_with_trustlines.functions.transfer(
            10, 0, [accounts[A], accounts[B]], b""
        ).transact({"from": accounts[A]})

    timestamp = web3.eth.getBlock("latest").timestamp
    timestamp += 3600 * 24 * 365

    chain.time_travel(timestamp)
    chain.mine_block()
    return currency_network_contract_with_trustlines


@pytest.fixture()
def currency_network_with_different_interests(
    web3, currency_network_contract_with_trustlines, accounts, chain
):
    """
    returns a currency network with updated balance accruing interests over one year
    the interests are not collected yet
    """
    for (A, B, clAB, clBA) in trustlines:
        currency_network_contract_with_trustlines.functions.transfer(
            clAB // 10, 0, [accounts[A], accounts[B]], b""
        ).transact({"from": accounts[A]})

    timestamp = web3.eth.getBlock("latest").timestamp
    timestamp += (3600 * 24 * 365) * 3

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


def event_id(event):
    return event["transactionHash"], event["logIndex"], event["blockHash"]


def get_interests_for_trustline(currency_network_contract, a, b):
    """Get all balance changes of a trustline because of interests"""
    balance_update_events = get_all_balance_update_events_for_trustline(
        currency_network_contract, a, b
    )

    timestamps = [
        currency_network_contract.web3.eth.getBlock(
            balance_update_event["blockNumber"]
        )["timestamp"]
        for balance_update_event in balance_update_events
    ]

    balances = get_all_balances_for_trustline(currency_network_contract, a, b)

    return [
        calculate_interests(balance, post_time - pre_time)
        for (balance, pre_time, post_time) in zip(
            balances[:-1], timestamps[:-1], timestamps[1:]
        )
    ]


def get_all_balance_update_events_for_trustline(currency_network_contract, a, b):
    """Get all balance update events of a trustline in sorted order"""
    forward_balance_update_events = currency_network_contract.events.BalanceUpdate().getLogs(
        fromBlock=0, argument_filters={"_from": a, "_to": b}
    )
    reverse_balance_update_events = currency_network_contract.events.BalanceUpdate().getLogs(
        fromBlock=0, argument_filters={"_from": b, "_to": a}
    )
    balance_update_events = []
    balance_update_events.extend(forward_balance_update_events)
    balance_update_events.extend(reverse_balance_update_events)
    balance_update_events.sort(
        key=lambda event: (event["blockNumber"], event["logIndex"])
    )
    return balance_update_events


def get_all_balances_for_trustline(currency_network_contract, a, b):
    """Get all balances of a trustline in sorted order from the view of a"""
    balance_update_events = get_all_balance_update_events_for_trustline(
        currency_network_contract, a, b
    )

    def balance(balance_update_event):
        if (
            balance_update_event["args"]["_from"] == a
            and balance_update_event["args"]["_to"] == b
        ):
            return balance_update_event["args"]["_value"]
        elif (
            balance_update_event["args"]["_from"] == b
            and balance_update_event["args"]["_to"] == a
        ):
            return -balance_update_event["args"]["_value"]
        else:
            RuntimeError("Unexpected balance update event")

    return [balance(event) for event in balance_update_events]


def get_balance_update_events_for_transfer(currency_network_contract, transfer_event):
    """Returns all balance update events in the correct order that belongs to the transfer event"""
    log_index = transfer_event["logIndex"]
    tx_hash = transfer_event["transactionHash"]

    receipt = currency_network_contract.web3.eth.getTransactionReceipt(tx_hash)
    balance_update_events = currency_network_contract.events.BalanceUpdate().processReceipt(
        receipt
    )

    sender = transfer_event["args"]["_from"]
    receiver = transfer_event["args"]["_to"]

    balance_events = []
    saw_sender_event = False
    saw_receiver_event = False

    # Search backwards for releated BalanceUpdate events
    for i in range(log_index - 1, -1, -1):
        for event in balance_update_events:
            if event["logIndex"] == i:
                balance_events.append(event)
                if event["args"]["_to"] == receiver:
                    saw_receiver_event = True
                if event["args"]["_from"] == sender:
                    saw_sender_event = True
                break
        if saw_sender_event and saw_receiver_event:
            break
    else:
        assert False, "Could not find all BalanceUpdate events"

    if balance_events[0]["args"]["_from"] != sender:
        # For the sender pays case, they are reverse
        balance_events.reverse()

    assert balance_events[0]["args"]["_from"] == sender
    assert balance_events[-1]["args"]["_to"] == receiver
    return balance_events


def get_transfer_path(currency_network_contract, transfer_event):
    """Returns the transfer path of the given transfer without the sender"""
    path_from_events = []
    transfer_events = get_balance_update_events_for_transfer(
        currency_network_contract, transfer_event
    )
    path_from_events.append(transfer_events[0]["args"]["_from"])
    for event in transfer_events:
        path_from_events.append(event["args"]["_to"])

    return path_from_events


def get_previous_balance(currency_network, a, b, balance_update_event):
    """Returns the balance before a given balance update event"""
    balance_update_events = get_all_balance_update_events_for_trustline(
        currency_network, a, b
    )
    index = 0
    # find the corresponding event
    for i, event in enumerate(balance_update_events):
        if event_id(balance_update_event) == event_id(event):
            index = i
            break
    else:
        raise RuntimeError("Could not find balance update")
    index -= 1

    if index < 0:
        return 0

    return get_all_balances_for_trustline(currency_network, a, b)[index]


def get_interest_at(currency_network_contract, balance_update_event):
    """Returns the occurred interests at a given balance event"""
    from_ = balance_update_event["args"]["_from"]
    to = balance_update_event["args"]["_to"]
    interests = get_interests_for_trustline(currency_network_contract, from_, to)
    balance_update_events = get_all_balance_update_events_for_trustline(
        currency_network_contract, from_, to
    )
    index = 0
    for i, event in enumerate(balance_update_events):
        if event_id(event) == event_id(balance_update_event):
            index = i
            break
    else:
        raise RuntimeError("Could not find balance update")

    index -= 1
    if index < 0:
        return 0

    return interests[index]


def get_delta_balances_of_transfer(currency_network_contract, transfer_event):
    """Returns the balance changes along the path because of a given transfer"""
    balance_update_events = get_balance_update_events_for_transfer(
        currency_network_contract, transfer_event
    )

    post_balances = []
    for event in balance_update_events:
        post_balances.append(event["args"]["_value"])

    pre_balances = []
    for event in balance_update_events:
        from_ = event["args"]["_from"]
        to = event["args"]["_to"]
        pre_balance = get_previous_balance(currency_network_contract, from_, to, event)
        pre_balances.append(pre_balance)

    interests = []
    for event in balance_update_events:
        interest = get_interest_at(currency_network_contract, event)
        interests.append(interest)

    # sender balance change
    delta_balances = [post_balances[0] - pre_balances[0] - interests[0]]

    # mediator balance changes
    for i in range(len(balance_update_events) - 1):
        next_tl_balance_change = (
            post_balances[i + 1] - pre_balances[i + 1] - interests[i + 1]
        )
        previous_tl_balance_change = post_balances[i] - pre_balances[i] - interests[i]
        delta_balances.append(next_tl_balance_change - previous_tl_balance_change)

    # receiver balance change
    delta_balances.append(-(post_balances[-1] - pre_balances[-1] - interests[-1]))

    return delta_balances


@pytest.mark.parametrize(
    "path, fee_payer",
    [
        ([0, 1], "sender"),
        ([0, 1, 2, 3], "sender"),
        ([3, 2, 1, 0], "sender"),
        ([0, 1], "receiver"),
        ([0, 1, 2, 3], "receiver"),
        ([3, 2, 1, 0], "receiver"),
    ],
)
def test_get_transfer_path_information(
    currency_network_contract_with_trustlines, accounts, path, fee_payer
):
    """
    test that we can get the path of a sent transfer from the transfer event
    """
    network = currency_network_contract_with_trustlines
    account_path = [accounts[i] for i in path]

    if fee_payer == "sender":
        network.functions.transfer(10, 100, account_path, b"").transact(
            {"from": account_path[0]}
        )
    elif fee_payer == "receiver":
        network.functions.transferReceiverPays(10, 100, account_path, b"").transact(
            {"from": account_path[0]}
        )
    else:
        assert False, "Invalid fee payer"

    transfer_event = network.events.Transfer().getLogs()[0]

    path_from_events = get_transfer_path(network, transfer_event)
    assert path_from_events == account_path


@pytest.mark.parametrize(
    "path, value, fee_payer, delta_values",
    [
        ([0, 1], 1, "sender", [-1, 1]),
        ([0, 1, 2, 3], 1, "sender", [-3, 1, 1, 1]),
        ([1, 2, 3, 4], 99, "sender", [-102, 2, 1, 99]),
        ([4, 3, 2, 1], 180, "sender", [-184, 2, 2, 180]),
        ([0, 1], 1, "receiver", [-1, 1]),
        ([0, 1, 2, 3], 3, "receiver", [-3, 1, 1, 1]),
        ([1, 2, 3, 4], 102, "receiver", [-102, 2, 1, 99]),
        ([4, 3, 2, 1], 184, "receiver", [-184, 2, 2, 180]),
    ],
)
def test_get_value_information(
    currency_network_with_pending_interests,
    accounts,
    path,
    value,
    fee_payer,
    delta_values,
):
    """
    test that we can get the values for sent, received and the fees from a transfer event
    """
    network = currency_network_with_pending_interests
    account_path = [accounts[i] for i in path]

    if fee_payer == "sender":
        network.functions.transfer(value, 1000, account_path, b"").transact(
            {"from": account_path[0]}
        )
    elif fee_payer == "receiver":
        network.functions.transferReceiverPays(value, 1000, account_path, b"").transact(
            {"from": account_path[0]}
        )
    else:
        assert False, "Invalid fee payer"

    transfer_event = network.events.Transfer().getLogs()[0]

    delta_balances = get_delta_balances_of_transfer(network, transfer_event)

    assert delta_balances == delta_values


@pytest.mark.parametrize(
    "path, fee_payer",
    [
        ([0, 1], "sender"),
        ([0, 1, 2, 3], "sender"),
        ([3, 2, 1, 0], "sender"),
        ([0, 1], "receiver"),
        ([0, 1, 2, 3], "receiver"),
        ([3, 2, 1, 0], "receiver"),
    ],
)
def test_get_balance_update_events(
    currency_network_contract_with_trustlines, accounts, path, fee_payer
):
    """Test that the found BalanceUpdateEvents are in the correct order"""
    path = [accounts[i] for i in path]
    network = currency_network_contract_with_trustlines

    if fee_payer == "sender":
        network.functions.transfer(10, 1000, path, b"").transact({"from": path[0]})
    elif fee_payer == "receiver":
        network.functions.transferReceiverPays(10, 1000, path, b"").transact(
            {"from": path[0]}
        )
    else:
        assert False, "Invalid fee payer"

    transfer_event = network.events.Transfer().getLogs()[0]

    balance_events = get_balance_update_events_for_transfer(network, transfer_event)

    sender = transfer_event["args"]["_from"]
    receiver = transfer_event["args"]["_to"]
    assert balance_events[0]["args"]["_from"] == sender
    assert balance_events[-1]["args"]["_to"] == receiver

    old_to = sender
    for event in balance_events:
        assert event["args"]["_from"] == old_to
        old_to = event["args"]["_to"]


@pytest.mark.parametrize(
    "years, interests", [([0, 1], [0, 2]), ([1, 4, 2, 3], [1, 9, 8, 19])]
)
def test_get_interests_for_trustline(
    currency_network_contract_with_trustlines, web3, chain, accounts, years, interests
):
    """Sending 10 with a time difference of x years where the interest rate is 10%
    """
    currency_network = currency_network_contract_with_trustlines
    currency_network.functions.transfer(
        10, 1000, [accounts[1], accounts[2]], b""
    ).transact({"from": accounts[1]})
    path = [accounts[0], accounts[1], accounts[2], accounts[3]]

    for year in years:
        timestamp = web3.eth.getBlock("latest").timestamp
        timestamp += (3600 * 24 * 365) * year + 1

        chain.time_travel(timestamp)
        chain.mine_block()
        currency_network.functions.transfer(9, 1000, path, b"").transact(
            {"from": accounts[0]}
        )
    balances = get_all_balances_for_trustline(
        currency_network, accounts[2], accounts[1]
    )

    assert (
        get_interests_for_trustline(currency_network, accounts[2], accounts[1])
        == interests
    )
    assert [
        ((i + 1) * 10 + sum(interests[:i])) for i, _ in enumerate(balances)
    ] == balances
