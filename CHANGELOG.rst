==========
Change Log
==========

`0.2.0`_ (not released)
-----------------------
* the python package `trustlines-contracts` is now superseded by the
  trustlines-contracts-deploy package. The old namespace tlcontracts is gone.
  The python code now lives in the tldeploy package. The tl-deploy script should
  work as before, but the installation got a lot easier (i.e. just pip install
  trustlines-contracts-deploy)

The rest of the changes are only interesting for developers:

* the internal tests do not rely on populus being installed. populus isn't a
  dependency of trustlines-contracts-deploy anymore.
* populus is still needed for smart contract compilation. It's being installed
  to a local virtualenv automatically by the newly introduced Makefile.

`0.1.3`_ (2018-09-04)
---------------------
* trustlines-contracts-deploy has been released to PyPI

`0.1.2`_ (2018-08-21)
---------------------
* trustlines-contracts has also been released to PyPI

`0.1.1`_ (2018-08-20)
---------------------
* trustlines-contracts-bin has been released to PyPI


.. _0.1.1: https://github.com/trustlines-network/contracts/compare/0.1.0...0.1.1
.. _0.1.2: https://github.com/trustlines-network/contracts/compare/0.1.1...0.1.2
.. _0.1.3: https://github.com/trustlines-network/contracts/compare/0.1.2...0.1.3
.. _0.2.0: https://github.com/trustlines-network/contracts/compare/0.1.3...0.2.0
