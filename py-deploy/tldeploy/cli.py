import click
import json
import pkg_resources
from web3 import Web3

from eth_utils import is_checksum_address, to_checksum_address

from .core import (deploy_network,
                   deploy_exchange,
                   deploy_unw_eth,
                   deploy_networks)


def report_version():
    for dist in ["trustlines-contracts-deploy", "trustlines-contracts-bin"]:
        msg = "{} {}".format(dist, pkg_resources.get_distribution(dist).version)
        click.echo(msg)


@click.group(invoke_without_command=True)
@click.option('--version', help='Prints the version of the software', is_flag=True)
@click.pass_context
def cli(ctx, version):
    """Commandline tool to deploy the Trustlines contracts"""
    if version:
        report_version()
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()


jsonrpc_option = click.option('--jsonrpc',
                              help='JsonRPC URL of the ethereum client',
                              default='http://127.0.0.1:8545',
                              show_default=True,
                              metavar='URL')

currency_network_contract_name_option = click.option(
    '--currency-network-contract-name',
    help='name of the currency network contract to deploy (only use this for testing)',
    default="CurrencyNetwork",
    hidden=True)


@cli.command(short_help='Deploy a currency network contract.')
@click.argument('name', type=str)
@click.argument('symbol', type=str)
@click.option('--decimals', help='Number of decimals of the network', default=4, show_default=True)
@click.option('--fee-rate', help='Imbalance fee rate of the currency network in percent', default=0.1,
              show_default=True)
@click.option('--default-interest-rate', help='Set the default interest rate in percent', default=0.,
              show_default=True)
@click.option('--custom-interests/--no-custom-interests',
              help='Allow users to set custom interest rates. Default interest rate must be zero', default=False,
              show_default=True)
@click.option('--prevent-mediator-interests', help='Disallow payments that would result in mediators paying interests',
              is_flag=True, default=False)
@click.option('--exchange-contract', help='Address of the exchange contract to use. [Optional] [default: None]',
              default=None, type=str, metavar='ADDRESS', show_default=True)
@currency_network_contract_name_option
@jsonrpc_option
def currencynetwork(name: str, symbol: str, decimals: int, jsonrpc: str, fee_rate: float, default_interest_rate: float,
                    custom_interests: bool, prevent_mediator_interests: bool, exchange_contract: str,
                    currency_network_contract_name: str):
    """Deploy a currency network contract with custom settings and optionally connect it to an exchange contract"""
    if exchange_contract is not None and not is_checksum_address(exchange_contract):
        raise click.BadParameter('{} is not a valid address.'.format(exchange_contract))

    if custom_interests and default_interest_rate != 0.0:
        raise click.BadParameter('Custom interests can only be set without a'
                                 ' default interest rate, but was {}%.'.format(default_interest_rate))

    if prevent_mediator_interests and not custom_interests:
        raise click.BadParameter('Prevent mediator interests is not necessary if custom interests are disabled.')

    fee_divisor = 1 / fee_rate * 100 if fee_rate != 0 else 0
    if int(fee_divisor) != fee_divisor:
        raise click.BadParameter('This fee rate is not usable')
    fee_divisor = int(fee_divisor)

    default_interest_rate = default_interest_rate * 100
    if int(default_interest_rate) != default_interest_rate:
        raise click.BadParameter('This default interest rate is not usable')
    default_interest_rate = int(default_interest_rate)

    web3 = Web3(Web3.HTTPProvider(jsonrpc, request_kwargs={"timeout": 180}))

    contract = deploy_network(
        web3,
        name,
        symbol,
        decimals,
        fee_divisor=fee_divisor,
        default_interest_rate=default_interest_rate,
        custom_interests=custom_interests,
        prevent_mediator_interests=prevent_mediator_interests,
        exchange_address=exchange_contract,
        currency_network_contract_name=currency_network_contract_name
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
            address=to_checksum_address(contract.address)
        )
    )


@cli.command(short_help='Deploy an exchange contract.')
@jsonrpc_option
def exchange(jsonrpc: str):
    """Deploy an exchange contract and a contract to wrap Ether into an ERC 20
  token.
    """
    web3 = Web3(Web3.HTTPProvider(jsonrpc, request_kwargs={"timeout": 180}))
    exchange_contract = deploy_exchange(web3)
    exchange_address = exchange_contract.address
    unw_eth_contract = deploy_unw_eth(web3, exchange_address=exchange_address)
    unw_eth_address = unw_eth_contract.address
    click.echo('Exchange: {}'.format(to_checksum_address(exchange_address)))
    click.echo('Unwrapping ether: {}'.format(to_checksum_address(unw_eth_address)))


@cli.command(short_help='Deploy contracts for testing.')
@click.option('--file', help='Output file for the addresses in json', default='',
              type=click.Path(dir_okay=False, writable=True))
@jsonrpc_option
@currency_network_contract_name_option
def test(jsonrpc: str, file: str, currency_network_contract_name: str):
    """Deploy three test currency network contracts connected to an exchange contract and an unwrapping ether contract.
    This can be used for testing"""

    network_settings = [
        {
            'name': 'Cash',
            'symbol': 'CASH',
            'decimals': 4,
            'fee_divisor': 1000,
            'default_interest_rate': 0,
            'custom_interests': True
        },
        {
            'name': 'Work Hours',
            'symbol': 'HOU',
            'decimals': 4,
            'fee_divisor': 0,
            'default_interest_rate': 1000,
            'custom_interests': False
        },
        {
            'name': 'Beers',
            'symbol': 'BEER',
            'decimals': 0,
            'fee_divisor': 0,
            'custom_interests': False
        }]

    web3 = Web3(Web3.HTTPProvider(jsonrpc, request_kwargs={"timeout": 180}))
    networks, exchange, unw_eth = deploy_networks(
        web3,
        network_settings,
        currency_network_contract_name=currency_network_contract_name)
    addresses = dict()
    network_addresses = [network.address for network in networks]
    exchange_address = exchange.address
    unw_eth_address = unw_eth.address
    addresses['networks'] = network_addresses
    addresses['exchange'] = exchange_address
    addresses['unwEth'] = unw_eth_address

    if file:
        with open(file, 'w') as outfile:
            json.dump(addresses, outfile)

    click.echo('Exchange: {}'.format(to_checksum_address(exchange_address)))
    click.echo('Unwrapping ether: {}'.format(to_checksum_address(unw_eth_address)))

    for settings, address in zip(network_settings, network_addresses):
        click.echo("CurrencyNetwork({settings}) at {address}".format(
            settings=settings,
            address=to_checksum_address(address)
        ))
