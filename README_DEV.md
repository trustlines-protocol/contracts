# Trustlines Smart Contract Platform

Smart Contracts, Unittests and Infrastructure for Trustlines App.

## Installation

The Smart Contracts can be installed separately from the other components of the Trustlines App.

### Prerequisites

 * Python 3.6
 * [pip](https://pip.pypa.io/en/stable/)

### Setup

 * pip install -r requirements.txt

### Usage

 * compilation: `populus compile`
 * unittest:    `pytest`
 * deploy:      `python deploy/deploy_testrpc.py`

For deployment a running _ethereumjs-testrpc_ (`testrpc`) with default values is mandatory.

### Integration

Each component of Trustlines has a Integration instruction which should enable any user to setup his own environment step-by-step.

#### Integrating Smart Contracts and Relay Server

*NOTE: we are assuming a running ethereumjs-testrpc (`testrpc`) instance with default settings.*

 * Follow the instructions for _Setup_ and _Usage_ above
 * Use the `CurrencyNetwork` address printed during deployment as argument for `python deploy/connect_wo_populus.py`
 * If there were no errors, the contracts are deployed correctly and can be used with any web3 connector