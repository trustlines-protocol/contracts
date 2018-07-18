# Trustlines Smart Contract Platform

Smart contracts, tests and deploy tools for Trustlines

## Prerequisites

 * Python 3.6 or up and dev dependencies
 * [pip](https://pip.pypa.io/en/stable/)
 * git

On ubuntu run
`apt install build-essential python3-dev python3-virtualenv virtualenv pkg-config libssl-dev automake autoconf libtool git
`

One of the dependencies used is the secp256k1 library. If you're using python 3.5 on linux you can skip the folowing step, since pypi contains binary packages for secp256k1. If not, you'll have to run the following to install the secp256k1 C library:

```
git clone https://github.com/bitcoin-core/secp256k1.git
cd secp256k1
./autogen.sh
./configure --enable-module-recovery
make
sudo make install
sudo ldconfig
```

## Deploy tools
This section explains how you can deploy your own curreny networks with custom settings and create your own trustlines setup.

## Prerequisites
To deploy the smart contracts for Trustlines you need an ethereum client which is synced to the chain you want to use. It also needs
to expose the JSON RPC endpoint.
Additionally you need an unlocked account with enough ether to pay for the contract deployment.

### Setup

 * Download and install the solidity compiler solc into bin for compiling the contracts
  `curl -L -o $HOME/bin/solc https://github.com/ethereum/solidity/releases/download/v0.4.21/solc-static-linux && chmod +x $HOME/bin/solc`

 * Clone this repositry with
 `git clone https://github.com/trustlines-network/contracts.git`
 `cd contracts`

 * Install the deploy tool with
 `pip install . -c constraints.txt`


### Deploy contracts

The tool `tl-deploy` allows you to deploy the relevant contracts.

Use `tl-deploy --help` to find out about the relevant commands or read further in the [deploy documentation](docs/deploy.md)


## Development

To start developing install the development dependencies into a venv with
`pip install -c constraints.txt -r requirements.txt`


### Compiling

The contracts can be compiled with
`populus compile`

### Testing
For testing we use pytest with a ethereum tester plugin. The tests can be run with
`python -m pytest tests`
