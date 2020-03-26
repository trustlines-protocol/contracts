|Code style: black|

Trustlines Smart Contract Platform
==================================

This documentation explains how to deploy Trustlines smart contracts,
for creating your own currency network and trustlines exchange.
The exchange functionality is not fully supported at this point.
The current documentation is written for an Ubuntu Linux system.

Prerequisites
-------------

-  Python 3.6 or up and dev dependencies
-  `pip <https://pip.pypa.io/en/stable/>`__
-  git

Run
``apt install build-essential python3-dev python3-virtualenv virtualenv pkg-config libssl-dev automake autoconf libtool git make libsecp256k1-dev``

Deployment tools
----------------

This section runs through the tooling necessary for deploying the
contracts.

Ethereum client
~~~~~~~~~~~~~~~

To deploy the Trustlines smart contracts, you need access to an ethereum client,
e.g. geth or parity, which is synced to the chain you want to use. The
client needs to expose the JSON RPC endpoint. Additionally you need an
account with enough ether to pay for the contract deployment.

Deployment setup
~~~~~~~~~~~~~~~~

Please run ``pip install trustlines-contracts-deploy`` to install the ``tl-deploy``
tool from PyPI. Solidity itself isn't needed anymore.

tl-deploy
~~~~~~~~~

The tool ``tl-deploy`` allows you to deploy the relevant contracts.

Use ``tl-deploy --help`` to find out about the relevant commands or read
further in the `deploy documentation <https://github.com/trustlines-protocol/contracts/blob/master/docs/deploy.md>`__

Development
-----------

To start developing install the development dependencies into a venv
with ``pip install -c constraints.txt -r requirements.txt``

Download and install the solidity compiler solc into bin for compiling the
contracts

   ``curl -L -o $HOME/bin/solc https://github.com/ethereum/solidity/releases/download/v0.5.8/solc-static-linux && chmod +x $HOME/bin/solc``

Compiling
~~~~~~~~~

The contracts can be compiled with ``make compile``. This will create a
file `contracts.json` with all the compiled contracts.


Testing
~~~~~~~

For testing we use pytest with an ethereum tester plugin. The tests can
be run with ``pytest``. Please not that this will recompile all contracts
automatically, there's no need to call ``make compile`` manually.

Installation
~~~~~~~~~~~~

Please run `make install` to install the trustlines-contracts-bin and
trustlines-contracts-deploy tool from the git checkout.

Dependencies
~~~~~~~~~~~~
To manage and pin the (sub)dependencies we use pip-tools. We create two requirements files,
one for the production environment (:code:`py-deploy/requirements.txt`) and one for all
development requirements (:code:`dev-requirements.txt`). The production dependencies are derived
from the dependencies defined in :code:`py-deploy/setup.py`. To add new dependencies, add them
to :code:`py-deploy/setup.py` and then run :code:`./compile-requirements`. The development requirements
are derived from :code:`dev-requirements.in`. To add new development dependencies, add them to this file and
then rerun :code:`./compile-requirements.sh`. To upgrade the dependencies in the created requirement files,
check out the available options for pip-tools and pass them to the compile script.
To update all dependencies, run :code:`./compile-requirements.sh --upgrade`.

Change log
----------

See `CHANGELOG <https://github.com/trustlines-protocol/contracts/blob/master/CHANGELOG.rst>`_.

.. |Code style: black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/ambv/black
