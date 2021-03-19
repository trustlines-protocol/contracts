import pytest
from tldeploy.core import deploy_currency_network_proxy, NetworkSettings


NETWORK_SETTINGS = NetworkSettings(
    name="TestCoin",
    symbol="T",
    custom_interests=True,
    expiration_time=2_000_000_000,
    fee_divisor=100,
)


@pytest.fixture(scope="session")
def upgraded_currency_network_implementation(deploy_contract):
    return deploy_contract(contract_identifier="CurrencyNetworkOwnableV2")


@pytest.fixture(scope="session")
def proxied_currency_network(
    web3, contract_assets, beacon_with_currency_network, owner, account_keys, accounts
):

    deployer_key = account_keys[1]
    deployer = accounts[1]

    proxied_currency_network = deploy_currency_network_proxy(
        web3=web3,
        network_settings=NETWORK_SETTINGS,
        beacon_address=beacon_with_currency_network.address,
        owner_address=owner,
        private_key=deployer_key,
    )
    proxied_currency_network = web3.eth.contract(
        address=proxied_currency_network.address,
        abi=contract_assets["CurrencyNetworkOwnable"]["abi"],
    )
    proxied_currency_network.functions.unfreezeNetwork().transact({"from": deployer})
    proxied_currency_network.functions.removeOwner().transact({"from": deployer})
    return proxied_currency_network


@pytest.fixture(scope="session")
def currency_network_adapter(proxied_currency_network, make_currency_network_adapter):
    return make_currency_network_adapter(proxied_currency_network)


@pytest.fixture(scope="session")
def currency_network_proxy(web3, proxied_currency_network, contract_assets):
    proxy = web3.eth.contract(
        address=proxied_currency_network.address,
        abi=contract_assets["AdministrativeProxy"]["abi"],
    )
    return proxy


@pytest.fixture(scope="session")
def upgrade_currency_network(
    beacon_with_currency_network, upgraded_currency_network_implementation, owner
):
    def upgrade():
        beacon_with_currency_network.functions.upgradeTo(
            upgraded_currency_network_implementation.address
        ).transact({"from": owner})

    return upgrade


def test_upgrade_currency_network_with_pending_trustlines_requests(
    currency_network_adapter,
    upgrade_currency_network,
    accounts,
):
    """Test that after upgrade the pending trustline requests are still pending"""
    trustline_initator = accounts[2]
    trustline_receiver = accounts[3]
    credit_given = 100
    credit_received = 200
    interest_given = 1
    interest_received = 2
    is_frozen = False

    currency_network_adapter.update_trustline(
        trustline_initator,
        trustline_receiver,
        creditline_given=credit_given,
        creditline_received=credit_received,
        interest_rate_given=interest_given,
        interest_rate_received=interest_received,
        is_frozen=is_frozen,
    )

    upgrade_currency_network()

    # Test that you can accept the trustline, i.e. it is still pending
    currency_network_adapter.update_trustline(
        trustline_receiver,
        trustline_initator,
        creditline_given=credit_received,
        creditline_received=credit_given,
        interest_rate_given=interest_received,
        interest_rate_received=interest_given,
        is_frozen=is_frozen,
    )

    assert currency_network_adapter.check_account(
        trustline_initator,
        trustline_receiver,
        creditline_given=credit_given,
        creditline_received=credit_received,
        interest_rate_given=interest_given,
        interest_rate_received=interest_received,
        is_frozen=is_frozen,
        balance=0,
    )


def test_upgrade_currency_network_meta_data(
    currency_network_adapter,
    upgrade_currency_network,
):
    """Test that the meta data remains after upgrade"""
    attributes = [
        "name",
        "symbol",
        "decimals",
        "is_initialized",
        "is_network_frozen",
        "expiration_time",
        "fee_divisor",
        "default_interest_rate",
        "custom_interests",
        "prevent_mediator_interests",
        "owner",
    ]
    old_values = dict()

    for attribute in attributes:
        old_values[attribute] = getattr(currency_network_adapter, attribute)

    upgrade_currency_network()

    for attribute in attributes:
        assert old_values[attribute] == getattr(currency_network_adapter, attribute)


def test_upgrade_currency_network_existing_trustlines(
    currency_network_adapter, upgrade_currency_network, accounts
):
    """Test that after upgrade the trustline still exists"""
    trustline_initator = accounts[2]
    trustline_receiver = accounts[3]
    credit_given = 100
    credit_received = 200
    interest_given = 1
    interest_received = 2
    is_frozen = False

    currency_network_adapter.update_trustline(
        trustline_initator,
        trustline_receiver,
        creditline_given=credit_given,
        creditline_received=credit_received,
        interest_rate_given=interest_given,
        interest_rate_received=interest_received,
        is_frozen=is_frozen,
        accept=True,
    )

    upgrade_currency_network()

    assert currency_network_adapter.check_account(
        trustline_initator,
        trustline_receiver,
        creditline_given=credit_given,
        creditline_received=credit_received,
        interest_rate_given=interest_given,
        interest_rate_received=interest_received,
        is_frozen=is_frozen,
        balance=0,
    )
    assert currency_network_adapter.get_friends(trustline_initator) == [
        trustline_receiver
    ]
    assert currency_network_adapter.get_friends(trustline_receiver) == [
        trustline_initator
    ]
    assert currency_network_adapter.get_users() == [
        trustline_initator,
        trustline_receiver,
    ]


def test_upgrade_currency_network_events(
    currency_network_adapter, upgrade_currency_network, accounts, chain
):
    """Test that after upgrade, we can still fetch previously emitted events"""
    # Open a trustline for events `TrustlineUpdateRequest`, and `TrustlineUpdate`
    trustline_initator = accounts[2]
    trustline_receiver = accounts[3]
    credit_given = 100
    credit_received = 200
    interest_given = 1
    interest_received = 2
    is_frozen = False

    currency_network_adapter.update_trustline(
        trustline_initator,
        trustline_receiver,
        creditline_given=credit_given,
        creditline_received=credit_received,
        interest_rate_given=interest_given,
        interest_rate_received=interest_received,
        is_frozen=is_frozen,
    )
    # Cancel the trustline update request for event `TrustlineUpdateCancel`
    currency_network_adapter.cancel_trustline_update(
        trustline_initator, trustline_receiver
    )
    currency_network_adapter.update_trustline(
        trustline_initator,
        trustline_receiver,
        creditline_given=credit_given,
        creditline_received=credit_received,
        interest_rate_given=interest_given,
        interest_rate_received=interest_received,
        is_frozen=is_frozen,
        accept=True,
    )

    # Make a transfer for events `BalanceUpdate, and `Transfer`
    transfer_initiator = accounts[2]
    transfer_receiver = accounts[3]
    transfer_extra_data = b"12345678"
    transfer_value = 50
    currency_network_adapter.transfer(
        transfer_value,
        path=[transfer_initiator, transfer_receiver],
        extra_data=transfer_extra_data,
    )

    # Freeze the network for NetworkFreeze event
    chain.time_travel(currency_network_adapter.expiration_time)
    chain.mine_block()
    currency_network_adapter.freeze_network()

    event_names = [
        "TrustlineUpdate",
        "TrustlineUpdateCancel",
        "TrustlineUpdateRequest",
        "BalanceUpdate",
        "NetworkFreeze",
        "Transfer",
        "NetworkUnfreeze",
        "OwnerRemoval",
    ]
    old_events = dict()
    for event_name in event_names:
        old_events[event_name] = currency_network_adapter.events(event_name)

    upgrade_currency_network()

    for event_name in event_names:
        new_events = currency_network_adapter.events(event_name)
        assert (
            len(new_events) != 0
        ), f"Did not get any events in upgraded contract for type {event_name}"
        assert old_events[event_name] == currency_network_adapter.events(event_name)
