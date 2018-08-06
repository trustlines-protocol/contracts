import click
import json
import pkg_resources

from eth_utils import is_checksum_address, to_checksum_address

from tlcontracts.deploy import (deploy_network,
                                get_project,
                                deploy_exchange,
                                deploy_unw_eth,
                                deploy_networks)
from tlcontracts.configurable_chain import ConfigurableChain


@click.group(invoke_without_command=True)
@click.option('--version', help='Prints the version of the software', is_flag=True)
@click.pass_context
def cli(ctx, version):
    """Commandline tool to deploy the Trustlines contracts"""
    if version:
        click.echo(pkg_resources.get_distribution('trustlines-contracts').version)
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()


jsonrpc_option = click.option('--jsonrpc',
                              help='JsonRPC URL of the ethereum client',
                              default='http://127.0.0.1:8545',
                              show_default=True,
                              metavar='URL')


@cli.command(short_help='Deploy a currency network contract.')
@click.argument('name', type=str)
@click.argument('symbol', type=str)
@click.option('--decimals', help='Number of decimals of the network', default=2, show_default=True)
@click.option('--fee-divisor', help='Imbalance fee divisor of the currency network', default=100, show_default=True)
@click.option('--exchange-contract', help='Address of the exchange contract to use [Optional]', default=None, type=str,
              metavar='ADDRESS')
@jsonrpc_option
def currencynetwork(name: str, symbol: str, decimals: int, jsonrpc: str, fee_divisor: int, exchange_contract: str):
    """Deploy a currency network contract with custom settings and optionally connect it to an exchange contract"""
    if exchange_contract is not None and not is_checksum_address(exchange_contract):
        raise click.BadParameter('{} is not a valid address'.format(exchange_contract))
    config_chain = create_config_chain(jsonrpc)
    with config_chain:
        contract = deploy_network(config_chain, name,
                                  symbol,
                                  decimals,
                                  fee_divisor=fee_divisor,
                                  exchange_address=exchange_contract)
        address = contract.address
    click.echo("CurrencyNetwork(name={name}, symbol={symbol}, "
               "decimals={decimals}, fee_divisor={fee_divisor}, "
               "exchange_address={exchange_address}): {address}".format(name=name,
                                                                        symbol=symbol,
                                                                        decimals=decimals,
                                                                        fee_divisor=fee_divisor,
                                                                        exchange_address=exchange_contract,
                                                                        address=to_checksum_address(address)
                                                                        ))


@cli.command(short_help='Deploy an exchange contract.')
@jsonrpc_option
def exchange(jsonrpc: str):
    """Deploy an exchange contract and a contract to wrap Ether into an ERC 20
  token.
    """
    config_chain = create_config_chain(jsonrpc)
    with config_chain:
        exchange_contract = deploy_exchange(config_chain)
        exchange_address = exchange_contract.address
        unw_eth_contract = deploy_unw_eth(config_chain, exchange_address=exchange_address)
        unw_eth_address = unw_eth_contract.address
    click.echo('Exchange: {}'.format(to_checksum_address(exchange_address)))
    click.echo('Unwrapping ether: {}'.format(to_checksum_address(unw_eth_address)))


@cli.command(short_help='Deploy contracts for testing.')
@click.option('--file', help='Output file for the addresses in json', default='',
              type=click.Path(dir_okay=False, writable=True))
@jsonrpc_option
def test(jsonrpc: str, file: str):
    """Deploy three test currency network contracts connected to an exchange contract and an unwrapping ether contract.
    This can be used for testing"""
    network_settings = [('Fugger', 'FUG', 2), ('Hours', 'HOU', 2), ('Testcoin', 'T', 6)]
    config_chain = create_config_chain(jsonrpc)
    with config_chain:
        networks, exchange, unw_eth = deploy_networks(config_chain, network_settings)
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

    for (name, symbol, decimals), address in zip(network_settings, network_addresses):
        click.echo("CurrencyNetwork(name={name}, symbol={symbol}, "
                   "decimals={decimals}): {address}".format(name=name,
                                                            symbol=symbol,
                                                            decimals=decimals,
                                                            address=to_checksum_address(address)
                                                            ))


def create_config_chain(jsonrpc: str) -> ConfigurableChain:
    project = get_project()
    chain = project.get_chain('testrpclocal')
    config_chain = ConfigurableChain.from_chain(chain)
    config_chain.set_json_rpc(jsonrpc)
    return config_chain
