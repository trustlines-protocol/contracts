.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

.. image:: https://circleci.com/gh/trustlines-protocol/contracts.svg?style=svg
    :target: https://circleci.com/gh/trustlines-protocol/contracts

.. image:: https://badges.gitter.im/Join%20Chat.svg
    :target: https://gitter.im/trustlines/community

Trustlines Smart Contract Platform
==================================
Introduction
------------

This repository contains the smart contracts implementing the Trustlines logic.
This includes:

- Currency Networks
- Exchanges
- Identity implementation, proxy, and proxy factory

It also includes deploy tools that can be used to deploy these contracts.
The deploy tools can be used via cli or as a python package to be built on top of.
The package tl-deploy used for deployment of the contracts additionally provides
an abstraction layer to identities and meta-transactions for delegates to use.

To have more information about trustlines in general, visit the `Trustlines Foundation website
<https://trustlines.network/>`__

Currency Networks
~~~~~~~~~~~~~~~~~

The currency network contracts represent the core logic of Trustlines.
They dictate how trustlines are opened, updated, and closed.
They also implement transfers in between users and how fees and interests are calculated.

Exchange
~~~~~~~~

The exchanges contracts are implementing an exchange which could be used to trade
the currency of a network for the currency of another network, an ERC20 token, or wrapped ether.
Their features are not currently fully supported by the protocol.

Identity
~~~~~~~~

The identity implementation contract allows to represent a user as a contract on a blockchain.
It enables the use of meta-transactions where a delegate pays the blockchain fee of a transaction
for a user. To reduce the costs of deploying an identity for a new user, we instead deploy a
proxy contract that points to a reference identity implementation.
This deployment is done by the identity proxy factory contract.

Installation
------------

The installation requires the following to be installed:

-  Python 3.6 or up and dev dependencies
-  `pip <https://pip.pypa.io/en/stable/>`__
-  git

To install them on Ubuntu, run::

    apt install build-essential python3-dev \
    python3-virtualenv virtualenv pkg-config libssl-dev \
    automake autoconf libtool git make libsecp256k1-dev

You can then install the deployment tool with::

    pip install trustlines-contracts-deploy

After that, you can run :code:`tl-deploy --help` to see the list of available
commands for deploying Trustlines contracts or read
further in the `deploy documentation <https://github.com/trustlines-protocol/contracts/blob/master/docs/deploy.md>`__

Start developing
----------------

To start developing on the smart contracts, you will need the solidity compiler solc version 0.5.8.
To download it into bin, run::

   curl -L -o $HOME/bin/solc https://github.com/ethereum/solidity/releases/download/v0.5.8/solc-static-linux && chmod +x $HOME/bin/solc

You can then clone the repository::

    git clone https://github.com/trustlines-protocol/contracts.git
    cd contracts

Then create and activate a fresh virtualenv::

    virtualenv -p python3 venv
    source venv/bin/activate

Finally, to install all needed dependencies and compiling the contracts use the following command::

    make install

Contributing
------------

Contributions are highly appreciated, but please check our `contributing guidelines </CONTRIBUTING.md>`__.

Release
-------

For versioning we use `setuptools-scm <https://pypi.org/project/setuptools-scm/>`_. This means the version number is
derived from git tags. To release a new version of the contracts on PyPI or Docker Hub, simply tag a commit with a valid version
number either via git, or from `github <https://github.com/trustlines-protocol/contracts/releases/new>`_.
Make sure to update the changelog accordingly and add all changes since the last released version.

Pre-commit hooks
~~~~~~~~~~~~~~~~

You should consider initializing the pre-commit hooks. The
installed git pre-commit hooks run flake8 and black among other things
when committing changes to the git repository ::

    pre-commit install
    pre-commit run -a

Testing
~~~~~~~

For testing we use pytest with an ethereum tester plugin. The tests can
be run with ``make test``. Please note that this will recompile all contracts
automatically, there's no need to call ``make compile`` manually.

You can also run end2end tests that will test how the contracts, `relay
<https://github.com/trustlines-protocol/relay>`__
, and `clientlib
<https://github.com/trustlines-protocol/clientlib>`__
work together. For more information about the end2end tests, see
`the end2end repository
<https://github.com/trustlines-protocol/end2end>`__

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

Release
~~~~~~~

How to release new contracts versions.

Change log
----------

See `CHANGELOG <https://github.com/trustlines-protocol/contracts/blob/master/CHANGELOG.rst>`_.
