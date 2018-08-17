# Trustlines deploy

The command line tool `tl-deploy` allows you to deploy the Trustlines contracts for both, creating a new currency network or a trustlines exchange. Make sure that you have a running ethereum client with enough ether as described [here](../README.md).

Use `tl-deploy --help` to find out about the relevant commands:

```
Usage: tl-deploy [OPTIONS] COMMAND [ARGS]...

  Commandline tool to deploy the Trustlines contracts

Options:
  --help  Show this message and exit.

Commands:
  currencynetwork  Deploy a currency network contract.
  exchange         Deploy an exchange contract.
  test             Deploy contracts for testing.
```

## Deploy a currency network
A currency network contract handles all trustlines with the same denomination. It allows for transfers between the users of this network.

You can deploy a currency network Testcoin with
`tl-deploy currencynetwork Testcoin TST`

To find out more about the possible options, use
`tl-deploy currencynetwork --help`
you will see the following output
```
Usage: tl-deploy currencynetwork [OPTIONS] NAME SYMBOL

  Deploy a currency network contract with custom settings and optionally
  connect it to an exchange contract.

Options:
  --decimals INTEGER           Number of decimals of the network  [default: 2]
  --fee-divisor INTEGER        Imbalance fee divisor of the currency network
                               [default: 100]
  --exchange-contract ADDRESS  Address of the exchange contract to use
                               [Optional]
  --jsonrpc URL                JsonRPC URL of the ethereum client  [default:
                               http://127.0.0.1:8545]
  --help                       Show this message and exit.

```

The mandatory arguments are the name and the symbol of the network.
All other parameters are optional as they have either default values or are not needed in some cases.

## Deploy an exchange
An exchange allows users of different currency networks to exchange 1. trustlines currencies, 2. trustlines currency for [ERC 20](https://github.com/ethereum/EIPs/blob/master/EIPS/eip-20.md) tokens and 3. trustlines currency for wrapped Ether.
This exchange is an extension to the [0x protocol](https://github.com/0xProject), adding support for Trustlines currencies.

You can deploy an exchange with

`tl-deploy exchange`

To get further information use

`tl-deploy exchange --help`

```
Usage: tl-deploy exchange [OPTIONS]

  Deploy an exchange contract and a contract to wrap Ether into an ERC 20
  token.

Options:
  --jsonrpc URL  JsonRPC URL of the ethereum client  [default:
                 http://127.0.0.1:8545]
  --help         Show this message and exit.
```
The address of this exchange can be used as input for the exchange-contract option when creating a currency network.
