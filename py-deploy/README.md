# Contracts Deploy Tool

This deploy tool can be used to deploy contracts of this repository on a blockchain and interact with them.
To read more about the contracts, readme the root directory [readme](../README.rst)

## Installation

You can install the deploy tool from this directory by running:

`pip install -r requirements.txt -e .`

You can otherwise install it by running

`pip install trustlines-contracts-deploy`

You can verify proper installation by running `tl-deploy --help`, which should bring up the help for the tool.

## Usage

There are 4 main commands for tl-deploy: `currencynetwork`, `exchange`, `identity-implementation`,
and `identity-proxy-factory`. There is also a command `test` that combines deployment of the previous contracts
used for testing purposes.

Different commands have different options depending on the specific contracts they deploy.
You can see these options by running the help on the command, e.g. `tl-deploy currencynetwork --help`.

However all the commands will:
 - need to connect to a blockchain node with option `--jsonrpc`,
 - use gas price set with `--gas-price`
 - use custom gas limit if set with `--gas`
 - start with nonce set by `--nonce`  or use the last nonce of sender if `--auto-nonce` is set
 - get access to a keystore file via `--keystore`
