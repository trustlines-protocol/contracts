# Trustlines deploy

The command line tool `tl-deploy` allows you to deploy the relevant Trustlines contracts. You need a running

Use `tl-deploy --help` to find out about the relevant commands

You will see the following output:

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

## Deploy a currency networks
A currency network contract handles all trustlines with the same denomination and allows for transfer between the users of this network.

You can deploy a currency network Testcoin with
`tl-deploy currencynetwork Testcoin TST`

To find out more about the possible options, use
`tl-deploy currencynetwork --help`
you will see the following output
```
Usage: tl-deploy currencynetwork [OPTIONS] NAME SYMBOL

  Deploy a currency network contract with custom settings and optionally
  connect it to an exchange contract

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
An exchange allows users of different currency networks to exchange trustlines money or to exchange trustlines money for tokens.
This includes ether via a ether wrapping contract. This exchange is based on the 0x protocol with an addition to support currency networks.

You can deploy an exchange with
`tl-deploy exchange`

To get further information use

`tl-deploy exchange --help`

```
Usage: tl-deploy exchange [OPTIONS]

  Deploy an exchange contract based on 0x that can work with Trustlines
  currency networks. This will also deploy a contract to wrap Ether into a
  token.

Options:
  --jsonrpc URL  JsonRPC URL of the ethereum client  [default:
                 http://127.0.0.1:8545]
  --help         Show this message and exit.
```
The address of this exchange can be used as input for the exchange-contract option when creating a currency network.




