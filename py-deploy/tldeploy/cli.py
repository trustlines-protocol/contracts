import json

import click
import pkg_resources
from deploy_tools.cli import (
    connect_to_json_rpc,
    gas_option,
    gas_price_option,
    get_nonce,
    jsonrpc_option,
    keystore_option,
    nonce_option,
    retrieve_private_key,
    validate_address,
)
from deploy_tools.transact import build_transaction_options
from eth_utils import is_checksum_address, to_checksum_address

import pendulum
from tldeploy.identity import (
    deploy_identity_implementation,
    deploy_identity_proxy_factory,
)

from .core import (
    deploy_exchange,
    deploy_network,
    deploy_networks,
    deploy_unw_eth,
    deploy_beacon,
    deploy_and_migrate_networks_from_file,
    NetworkSettings,
)
from tldeploy.migration import migrate_networks, verify_networks_migrations


def report_version():
    for dist in ["trustlines-contracts-deploy", "trustlines-contracts-bin"]:
        msg = "{} {}".format(dist, pkg_resources.get_distribution(dist).version)
        click.echo(msg)


def validate_date(ctx, param, value):
    if value is None:
        return None
    try:
        return pendulum.parse(value)
    except pendulum.parsing.exceptions.ParserError as e:
        raise click.BadParameter(
            f'The parameter "{value}" cannot be parsed as a date. (Try e.g. "2020-09-28", "2020-09-28T13:56")'
        ) from e


@click.group(invoke_without_command=True)
@click.option("--version", help="Prints the version of the software", is_flag=True)
@click.pass_context
def cli(ctx, version):
    """Commandline tool to deploy the Trustlines contracts"""
    if version:
        report_version()
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()


currency_network_contract_name_option = click.option(
    "--currency-network-contract-name",
    help="name of the currency network contract to deploy, "
    "(e.g. CurrencyNetworkOwnable, CurrencyNetwork, or  TestCurrencyNetwork)",
    default="CurrencyNetwork",
    hidden=False,
)


@cli.command(short_help="Deploy a currency network contract.")
@click.argument("name", type=str)
@click.argument("symbol", type=str)
@click.option(
    "--decimals", help="Number of decimals of the network", default=4, show_default=True
)
@click.option(
    "--fee-rate",
    help="Imbalance fee rate of the currency network in percent",
    default=0.1,
    show_default=True,
)
@click.option(
    "--default-interest-rate",
    help="Set the default interest rate in percent",
    default=0.0,
    show_default=True,
)
@click.option(
    "--custom-interests/--no-custom-interests",
    help="Allow users to set custom interest rates. Default interest rate must be zero",
    default=False,
    show_default=True,
)
@click.option(
    "--prevent-mediator-interests",
    help="Disallow payments that would result in mediators paying interests",
    is_flag=True,
    default=False,
)
@click.option(
    "--exchange-contract",
    help="Address of the exchange contract to use. [Optional] [default: None]",
    default=None,
    type=str,
    metavar="ADDRESS",
    show_default=True,
)
@currency_network_contract_name_option
@click.option(
    "--expiration-time",
    help=(
        "Expiration time of the currency network after which it will be frozen (0 means disabled). "
        "Per default the network does not expire."
    ),
    required=False,
    type=int,
)
@click.option(
    "--expiration-date",
    help=(
        "Expiration date of the currency network after which it will be frozen "
        "(e.g. '2020-09-28', '2020-09-28T13:56'). "
        "Per default the network does not expire."
    ),
    type=str,
    required=False,
    metavar="DATE",
    callback=validate_date,
)
@jsonrpc_option
@gas_option
@gas_price_option
@nonce_option
@keystore_option
def currencynetwork(
    name: str,
    symbol: str,
    decimals: int,
    jsonrpc: str,
    fee_rate: float,
    default_interest_rate: float,
    custom_interests: bool,
    prevent_mediator_interests: bool,
    exchange_contract: str,
    currency_network_contract_name: str,
    expiration_time: int,
    expiration_date: pendulum.DateTime,
    gas: int,
    gas_price: int,
    nonce: int,
    keystore: str,
):
    """Deploy a currency network contract with custom settings and optionally connect it to an exchange contract"""
    if exchange_contract is not None and not is_checksum_address(exchange_contract):
        raise click.BadParameter("{} is not a valid address.".format(exchange_contract))

    if custom_interests and default_interest_rate != 0.0:
        raise click.BadParameter(
            "Custom interests can only be set without a"
            " default interest rate, but was {}%.".format(default_interest_rate)
        )

    if prevent_mediator_interests and not custom_interests:
        raise click.BadParameter(
            "Prevent mediator interests is not necessary if custom interests are disabled."
        )

    if expiration_date is not None and expiration_time is not None:
        raise click.BadParameter(
            "Both --expiration-date and --expiration-times have been specified."
        )

    if expiration_date is None and expiration_time is None:
        expiration_time = 0

    if expiration_date is not None:
        expiration_time = int(expiration_date.timestamp())

    fee_divisor = 1 / fee_rate * 100 if fee_rate != 0 else 0
    if int(fee_divisor) != fee_divisor:
        raise click.BadParameter("This fee rate is not usable")
    fee_divisor = int(fee_divisor)

    default_interest_rate = default_interest_rate * 100
    if int(default_interest_rate) != default_interest_rate:
        raise click.BadParameter("This default interest rate is not usable")
    default_interest_rate = int(default_interest_rate)

    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=gas, gas_price=gas_price, nonce=nonce
    )

    network_settings = NetworkSettings(
        name=name,
        symbol=symbol,
        decimals=decimals,
        fee_divisor=fee_divisor,
        default_interest_rate=default_interest_rate,
        custom_interests=custom_interests,
        prevent_mediator_interests=prevent_mediator_interests,
        expiration_time=expiration_time,
    )

    contract = deploy_network(
        web3,
        network_settings,
        exchange_address=exchange_contract,
        currency_network_contract_name=currency_network_contract_name,
        transaction_options=transaction_options,
        private_key=private_key,
    )

    click.echo(
        "CurrencyNetwork(name={name}, symbol={symbol}, "
        "decimals={decimals}, fee_divisor={fee_divisor}, "
        "default_interest_rate={default_interest_rate}, "
        "custom_interests={custom_interests}, "
        "prevent_mediator_interests={prevent_mediator_interests}, "
        "exchange_address={exchange_address}): {address}".format(
            name=name,
            symbol=symbol,
            decimals=decimals,
            fee_divisor=fee_divisor,
            default_interest_rate=default_interest_rate,
            custom_interests=custom_interests,
            prevent_mediator_interests=prevent_mediator_interests,
            exchange_address=exchange_contract,
            address=to_checksum_address(contract.address),
        )
    )


@cli.command(short_help="Deploy an exchange contract.")
@jsonrpc_option
@gas_option
@gas_price_option
@nonce_option
@keystore_option
def exchange(jsonrpc: str, gas: int, gas_price: int, nonce: int, keystore: str):
    """Deploy an exchange contract and a contract to wrap Ether into an ERC 20
    token.
    """
    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=gas, gas_price=gas_price, nonce=nonce
    )
    exchange_contract = deploy_exchange(
        web3=web3, transaction_options=transaction_options, private_key=private_key
    )
    exchange_address = exchange_contract.address
    unw_eth_contract = deploy_unw_eth(
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
        exchange_address=exchange_address,
    )
    unw_eth_address = unw_eth_contract.address
    click.echo("Exchange: {}".format(to_checksum_address(exchange_address)))
    click.echo("Unwrapping ether: {}".format(to_checksum_address(unw_eth_address)))


@cli.command(short_help="Deploy an identity implementation contract.")
@jsonrpc_option
@gas_option
@gas_price_option
@nonce_option
@keystore_option
def identity_implementation(
    jsonrpc: str, gas: int, gas_price: int, nonce: int, keystore: str
):
    """Deploy an identity contract without initializing it. Can be used as the implementation for deployed
    identity proxies.
    """
    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=gas, gas_price=gas_price, nonce=nonce
    )
    identity_implementation = deploy_identity_implementation(
        web3=web3, transaction_options=transaction_options, private_key=private_key
    )
    click.echo(
        "Identity implementation: {}".format(
            to_checksum_address(identity_implementation.address)
        )
    )


@cli.command(short_help="Deploy an identity proxy factory.")
@jsonrpc_option
@gas_option
@gas_price_option
@nonce_option
@keystore_option
def identity_proxy_factory(
    jsonrpc: str, gas: int, gas_price: int, nonce: int, keystore: str
):
    """Deploy an identity proxy factory, which can be used to create proxies for identity contracts."""

    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=gas, gas_price=gas_price, nonce=nonce
    )
    identity_proxy_factory = deploy_identity_proxy_factory(
        web3=web3, transaction_options=transaction_options, private_key=private_key
    )
    click.echo(
        "Identity proxy factory: {}".format(
            to_checksum_address(identity_proxy_factory.address)
        )
    )


@cli.command(short_help="Deploy contracts for testing.")
@click.option(
    "--file",
    help="Output file for the addresses in json",
    default="",
    type=click.Path(dir_okay=False, writable=True),
)
@jsonrpc_option
@gas_option
@gas_price_option
@nonce_option
@keystore_option
@currency_network_contract_name_option
def test(
    jsonrpc: str,
    file: str,
    gas: int,
    gas_price: int,
    nonce: int,
    keystore: str,
    currency_network_contract_name: str,
):
    """Deploy three test currency network contracts connected to an exchange contract and an unwrapping ether contract.
    Also deploys an identity proxy factory and an identity implementation contract.
    This can be used for testing"""

    expiration_time = 4_102_444_800  # 01/01/2100

    network_settings = [
        NetworkSettings(
            name="Cash",
            symbol="CASH",
            decimals=4,
            fee_divisor=1000,
            default_interest_rate=0,
            custom_interests=True,
            expiration_time=expiration_time,
            prevent_mediator_interests=False,
        ),
        NetworkSettings(
            name="Work Hours",
            symbol="HOU",
            decimals=4,
            fee_divisor=0,
            default_interest_rate=1000,
            custom_interests=False,
            expiration_time=expiration_time,
            prevent_mediator_interests=False,
        ),
        NetworkSettings(
            name="Beers",
            symbol="BEER",
            decimals=0,
            fee_divisor=0,
            default_interest_rate=0,
            custom_interests=False,
            expiration_time=expiration_time,
            prevent_mediator_interests=False,
        ),
    ]

    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=gas, gas_price=gas_price, nonce=nonce
    )
    networks, exchange, unw_eth = deploy_networks(
        web3,
        network_settings,
        currency_network_contract_name=currency_network_contract_name,
        transaction_options=transaction_options,
    )
    identity_implementation = deploy_identity_implementation(
        web3=web3, transaction_options=transaction_options, private_key=private_key
    )
    second_identity_implementation = deploy_identity_implementation(
        web3=web3, transaction_options=transaction_options, private_key=private_key
    )
    identity_proxy_factory = deploy_identity_proxy_factory(
        web3=web3, transaction_options=transaction_options, private_key=private_key
    )
    addresses = dict()
    network_addresses = [network.address for network in networks]
    exchange_address = exchange.address
    unw_eth_address = unw_eth.address
    addresses["networks"] = network_addresses
    addresses["exchange"] = exchange_address
    addresses["unwEth"] = unw_eth_address
    # TODO: remove address["identityImplementation"], left for backward compatibility
    addresses["identityImplementation"] = identity_implementation.address
    addresses["identityProxyFactory"] = identity_proxy_factory.address
    addresses["identityImplementations"] = [
        identity_implementation.address,
        second_identity_implementation.address,
    ]

    if file:
        with open(file, "w") as outfile:
            json.dump(addresses, outfile)

    click.echo("Exchange: {}".format(to_checksum_address(exchange_address)))
    click.echo("Unwrapping ether: {}".format(to_checksum_address(unw_eth_address)))
    click.echo(
        "Identity proxy factory: {}".format(
            to_checksum_address(identity_proxy_factory.address)
        )
    )
    click.echo(
        "Identity implementations: {} and {}".format(
            to_checksum_address(identity_implementation.address),
            to_checksum_address(second_identity_implementation.address),
        )
    )
    for settings, address in zip(network_settings, network_addresses):
        click.echo(
            "CurrencyNetwork({settings}) at {address}".format(
                settings=settings, address=to_checksum_address(address)
            )
        )


@cli.command(short_help="Migrate old currency networks to new ones.")
@click.option(
    "--old-addresses",
    "old_addresses_file_path",
    help="Path to a csv file with addresses of old currency networks, order and number must match with new addresses",
    default="",
    type=click.Path(dir_okay=False, writable=True),
)
@click.option(
    "--new-addresses",
    "new_addresses_file_path",
    help="Path to a csv file with addresses of new currency networks, order and number must match with old addresses",
    default="",
    type=click.Path(dir_okay=False, writable=True),
)
@jsonrpc_option
@gas_price_option
@nonce_option
@keystore_option
def migration(
    old_addresses_file_path: str,
    new_addresses_file_path: str,
    jsonrpc: str,
    gas_price: int,
    nonce: int,
    keystore: str,
):
    """Used to migrate old currency networks to new ones
    It will fetch information about users in the old contract and set them in the one
    The address files should contain currency network addresses with
    address matching from one file to the other from top to bottom"""

    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=None, gas_price=gas_price, nonce=nonce
    )
    migrate_networks(
        web3,
        old_addresses_file_path,
        new_addresses_file_path,
        transaction_options,
        private_key,
    )


@cli.command(short_help="Verify migration from old currency networks to new ones.")
@click.option(
    "--old-addresses",
    "old_addresses_file_path",
    help="Path to a csv file with addresses of old currency networks, order and number must match with new addresses",
    default="",
    type=click.Path(dir_okay=False, writable=True),
)
@click.option(
    "--new-addresses",
    "new_addresses_file_path",
    help="Path to a csv file with addresses of new currency networks, order and number must match with old addresses",
    default="",
    type=click.Path(dir_okay=False, writable=True),
)
@jsonrpc_option
def verify_migration(
    old_addresses_file_path: str, new_addresses_file_path: str, jsonrpc: str
):
    """Used to verify migration of old currency networks to new ones
    The address files should contain currency network addresses with
    address matching from one file to the other from top to bottom"""

    web3 = connect_to_json_rpc(jsonrpc)

    verify_networks_migrations(web3, old_addresses_file_path, new_addresses_file_path)


@cli.command(short_help="Deploy a new beacon contract")
@click.option(
    "--implementation",
    "implementation_address",
    help="Address of the implementation contract the beacon will point to",
    required=True,
    type=str,
    callback=validate_address,
)
@click.option(
    "--owner",
    "owner_address",
    help="Address of the owner of the beacon to be deployed",
    required=True,
    type=str,
    callback=validate_address,
)
@jsonrpc_option
@gas_price_option
@nonce_option
@keystore_option
def beacon(
    implementation_address: str,
    owner_address: str,
    jsonrpc: str,
    gas_price: int,
    nonce: int,
    keystore: str,
):
    """Used to deploy an owned beacon pointing to an implementation address"""

    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=None, gas_price=gas_price, nonce=nonce
    )
    beacon = deploy_beacon(
        web3,
        implementation_address,
        owner_address,
        private_key=private_key,
        transaction_options=transaction_options,
    )
    click.secho(
        f"Beacon successfully deployed at address {beacon.address} with owner {beacon.functions.owner().call()}"
    )


@cli.command(
    short_help="Deploy new currrency networks and migrate old ones to deployed ones."
)
@click.option(
    "--addresses-file",
    "addresses_file_path",
    help="Path to a csv file with addresses of old currency networks, order and number must match with new addresses",
    default="",
    type=click.Path(dir_okay=False, writable=True),
)
@click.option(
    "--beacon",
    "beacon_address",
    help="Address of the beacon contract the proxies will point to",
    required=True,
    type=str,
    callback=validate_address,
)
@click.option(
    "--owner",
    "owner_address",
    help="Address of the owner of the proxies to be deployed",
    required=True,
    type=str,
    callback=validate_address,
)
@click.option(
    "--output",
    "output_file_path",
    help="Path of the file to print the mapping of old network to new network to",
    default="output.json",
    type=click.Path(dir_okay=False, writable=True),
)
@jsonrpc_option
@gas_price_option
@nonce_option
@keystore_option
def deploy_and_migrate(
    addresses_file_path: str,
    output_file_path: str,
    beacon_address: str,
    owner_address: str,
    jsonrpc: str,
    gas_price: int,
    nonce: int,
    keystore: str,
):
    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)
    nonce = get_nonce(web3=web3, nonce=nonce, private_key=private_key)
    transaction_options = build_transaction_options(
        gas=None, gas_price=gas_price, nonce=nonce
    )

    deploy_and_migrate_networks_from_file(
        web3=web3,
        addresses_file_path=addresses_file_path,
        beacon_address=beacon_address,
        owner_address=owner_address,
        private_key=private_key,
        transaction_options=transaction_options,
        output_file_path=output_file_path,
    )
