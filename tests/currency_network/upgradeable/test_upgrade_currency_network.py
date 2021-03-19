import pytest
from tldeploy.core import deploy_currency_network_proxy, NetworkSettings


NETWORK_SETTINGS = NetworkSettings(name="TestCoin", symbol="T", custom_interests=True)


@pytest.fixture(scope="session")
def upgraded_currency_network_implementation(deploy_contract):
    return deploy_contract(contract_identifier="CurrencyNetworkBasicV2")


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
def currency_network_proxy(web3, proxied_currency_network, contract_assets):
    proxy = web3.eth.contract(
        address=proxied_currency_network.address,
        abi=contract_assets["AdministrativeProxy"]["abi"],
    )
    return proxy


def test_upgrade_currency_network_with_pending_trustlines_requests(
    proxied_currency_network,
    beacon_with_currency_network,
    upgraded_currency_network_implementation,
    owner,
    accounts,
):
    trustline_initator = accounts[2]
    trustline_receiver = accounts[3]
    credit_given = 100
    credit_received = 200
    interest_given = 1
    interest_received = 2
    is_frozen = False

    proxied_currency_network.functions.updateTrustline(
        trustline_receiver,
        credit_given,
        credit_received,
        interest_given,
        interest_received,
        is_frozen,
    ).transact({"from": trustline_initator})

    beacon_with_currency_network.functions.upgradeTo(
        upgraded_currency_network_implementation.address
    ).transact({"from": owner})

    # Test that you can accept the trustline, i.e. it is still pending
    proxied_currency_network.functions.updateTrustline(
        trustline_initator,
        credit_received,
        credit_given,
        interest_received,
        interest_given,
        is_frozen,
    ).transact({"from": trustline_receiver})

    (
        effective_credit_given,
        effective_credit_received,
        effective_interest_given,
        effective_interest_received,
        effective_is_frozen,
        effective_mtime,
        effective_balance,
    ) = proxied_currency_network.functions.getAccount(
        trustline_initator, trustline_receiver
    ).call(
        {"from": trustline_initator}
    )

    assert effective_credit_given == credit_given
    assert effective_credit_received == credit_received
    assert effective_interest_given == interest_given
    assert effective_interest_received == interest_received
    assert effective_is_frozen == is_frozen
    assert effective_balance == 0
