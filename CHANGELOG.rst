==========
Change Log
==========
`next`_ (unreleased)
-----------------------

`1.1.7`_ (2020-10-12)
-----------------------
* Fixed: packing of contracts in trustlines-contracts-bin,
  it was not working properly when installed in editable mode.
* Added: Natspec missing to some contracts functions
* Updated: dependencies updated, notably contract-deploy-tools==0.8.0 and web3==5.12.1

`1.1.6`_ (2020-08-24)
-----------------------
* Added: function for delegate to find the implementation address of an identity proxy:
  `Delegate.get_implementation_address(identity_address)`
* Added: Deploy a second identity implementation contract in the the `tldeploy test` command.
  this can be used for testing the update of identity implementations.

`1.1.5`_ (2020-07-21)
-----------------------
* Add means to get contracts.json from py-bin: `from tlbin import load_packaged_contracts`

`1.1.4`_ (2020-04-15)
-----------------------
* Fix bug in interests calculations that would cause the balance to flip sign for big values of negative interests.
  Set the balance to 0 when this should happen instead.

`1.1.3`_ (2020-02-28)
-----------------------
* Allow to set transaction options like gasLimit and gasPrice when deploying identity contracts
`1.1.2`_ (2020-02-26)
-----------------------
* Allow to set transaction options like gasLimit and gasPrice when sending a meta transaction

`1.1.1`_ (2020-02-25)
-----------------------
* Add function of Delegate `get_meta_transaction_status`

`1.1.0`_ (2020-02-17)
-----------------------
* Add `timeLimit`, `operationType`, and `feeRecipient` to signature of `executeTransaction` (BREAKING)
* Add `chainId` to constructor of `identityProxyFactory` used by identities to verify the chainId of meta-tx (BREAKING)
* Add `version` to identity contract used to verify the `version` of meta-tx (BREAKING)
* Add function `execute()` in identity to execute a transaction from the owner without having to check a signature and account for fees
* Add function `cancelTransaction(txHash)` in identity to invalidate meta-transactions with hash `txHash`
* Add mechanism to accept every `nonce > 2**255` to allow for replaying transactions that would otherwise have the same hash
* Update `validateNonce()` in identity to also validate if the hash was used
* Update signature of `executeTransaction` in identity: replaced `fees` with `baseFee`, `gasPrice`, and `gasLimit` (BREAKING)
* Update `identity.py` to match new `executeTransaction` signature (BREAKING)
* Rename `FeesPaid` event of identity to `FeePayment` (BREAKING)

`1.0.0`_ (2019-12-30)
-----------------------
* Add function `cancelTrustlineUpdate(address counterparty)` to cancel a trustline update request in between msg.sender and counterparty.
* Add `applyInterests` external function to manually apply interests
* Change signature of functions `transfer`, `transferFrom`, `debitTransfer`, `transferReceiverPays`
  so that it no longer takes `_to` argument but takes a complete path including sender and receiver (BREAKING)
* Change: Lower the absolute max value of balances from `2**71 - 1` to `2**64 - 1` to match maximum transferable value
* Change the way how to add authorized addresses to call `transferFrom`. Users can now add an authorized address
  for themselves
* Remove self destruct from Currency Network
* Remove owner from Currency Network
* Remove boolean return values from Currency Network functions.
* Remove ERC20 related functions: `spendable`, `spendableTo`, `totalSupply`, and `balanceOf`
* Remove function `updateTrustlineDefaultInterests`
* Remove unused outstanding fees field in trustline (BREAKING)
* Bugfix: emit Transfer event also on `closeTrustlineViaTriangularTransfer`
* Bugfix: Prevent overflows in `closeTrustlineViaTriangularTransfer`
* Bugfix: Prevent overflows in interests calculation
* Bugfix: Prevent overflows in debt tracking


`0.10.1`_ (2019-11-18)
-----------------------
* Add `NetworkFreeze` event when freezing a currency network
* Add `debitTransfer` function for creditors to collect debts
* Add `CurrencyNetworkAdded` event to registry when networks are registered after the first time

`0.10.0`_ (2019-11-05)
-----------------------
* Add commandline option based on contract-deploy-tools to sign transactions based on a keystore file
* Add commandline option based on contract-deploy-tools to set nonce, gas limit and gas price
* Remove setAccount function in currency network (BREAKING).

`0.9.3`_ (2019-10-10)
-----------------------
* Fix `deploy_proxied_identity` by getting the deployed contract address via deployment transaction receipt events. This solves a bug where the wrong address would be returned when deploying two proxies in the same block
* Expiry date of currency networks is now optional. The default argument in tl-deploy is no expiry date.

`0.9.2`_ (2019-10-04)
-----------------------
* Fix `deploy_proxied_identity` by adding the missing file `identity-proxy.json` containing bytecode for the contract deployment to package

`0.9.1`_ (2019-10-04)
-----------------------
* Added proxy and factory contracts
* Added method `deploy_proxied_identity` in `tldeploy.identity` to deploy an identity at a pre-computable address using a factory
* Added showcase tests for getting information out of events

`0.9.0`_ (2019-09-11)
-----------------------
* Add currency network registry that can be used to register curency networks and list registered networks
* Change CurrencyNetworkInterface into an actual interface implementing ERC-165
* Add function to track debt within currency networks, this can be used to represent a payment when there is no path in between two addresses
* Change function for executing meta-transaction in identity contracts: Add fields to meta-transaction to pay for transaction(BREAKING)

`0.8.0`_ (2019-09-02)
-----------------------
* Currency networks are only initializable once
* Currency networks have an expiry date, after which all trustlines are frozen
* Trustlines agreements can be updated by users to be frozen
* Frozen trustlines can not be used for transfers or updated until unfrozen
* Add rules and accounting for user onboarding
* Trustlines cannot be set by owner of currency network unless `accountManagementEnabled` is set to true

`0.7.0`_ (2019-08-06)
-----------------------
* Add missing BalanceUpdate on trustlines changes
* Update the contracts to solc 0.5.8.
* Add extraData to transfer and Transfer events

`0.6.3`_ (2019-06-05)
-----------------------
* Copyright has been transferred to the trustlines foundation
* format code with black
* relax requirements in py-deploy in order to make it compatible with newer web3
  releases

`0.6.2`_ (2019-02-13)
-----------------------
* Add a function to query the nonce so that the delegator can provided it

`0.6.1`_ (2019-02-08)
-----------------------
* Add deploy identity function
* Add estimate gas for meta transaction
* Add validation to delegator
* Add error messages to requires

`0.6.0`_ (2019-02-05)
-----------------------
* Add an identity contract implementation and a way for delegators to execute
  meta transactions on behalf users using these identity contracts. The result
  is that users do not have to pay for gas directly.

`0.5.1`_ (2019-01-23)
-----------------------
* Fix internal version dependency, 0.5.0 was broken

`0.5.0`_ (2019-01-23)
-----------------------
* Remove old populus dependency and substitute it with contract-deploy-tools

`0.4.0`_ (2018-12-10)
-----------------------
* Remove the fees on the last hop

  A user now only has to pay fees to the true mediators and not anymore to the receiver.

* Add transfer function where receiver pays the fees

  It is now possible to make payments, where the receiver will pay the fees.

* Round up fees

  We are now properly rounding up the fees, where before we used an own formular that was
  already close to rounding up.

* Bug Fix #159
  that an old trustline request could be accepted

`0.3.3`_ (2018-11-28)
-----------------------
* Bug fix deploy tool so that it is possible to deploy a network with zero fees
* First version of trustlines-contracts-abi on npm.

`0.3.2`_ (2018-11-26)
-----------------------
* Optimize gas cost of contracts

`0.3.1`_ (2018-11-13)
-----------------------
* Fix a dependency issue

`0.3.0`_ (2018-11-12)
-----------------------
* Added interests to currency networks

  A trustline now also consists of two interest rates given by the two parties to each other.
  These interest rates are used to calculate occured interests between the two parties. The balance
  including the interests is updated whenever the balance (because of a transfer) or one of
  the interest rates (because of a trustline update) changes. To calculate the interests we
  approximate Continuous Compounding with a taylor series and use the current timestamp and
  the timestamp of the last update.

* Added interest settings to deploy tool

  The deploy tool now allows deploying networks with different interests settings. The current options
  are: Default interests: If this is set, every trustline has the same interest rate.
  Custom interest: If this is set, every user can decide which interest rate he want to give.
  Prevent mediator interests: Safe setting to prevent mediators from paying interests for
  mediated transfer by disallowing certain transfers.

* Close a trustline

  Added a new function to do a triangular payment to close a trustline. This will set the balance
  between two user to zero and also removes all information about this trustline. This is still work
  in progress and might change.

`0.2.0`_ (2018-09-19)
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
* The field capacityImbalanceFeeDivisor was made public. As a result, there's
  now a getter function for it in the ABI.

`0.1.3`_ (2018-09-04)
---------------------
* trustlines-contracts-deploy has been released to PyPI

`0.1.2`_ (2018-08-21)
---------------------
* trustlines-contracts has also been released to PyPI

`0.1.1`_ (2018-08-20)
---------------------
* trustlines-contracts-bin has been released to PyPI


.. _0.1.1: https://github.com/trustlines-protocol/contracts/compare/0.1.0...0.1.1
.. _0.1.2: https://github.com/trustlines-protocol/contracts/compare/0.1.1...0.1.2
.. _0.1.3: https://github.com/trustlines-protocol/contracts/compare/0.1.2...0.1.3
.. _0.2.0: https://github.com/trustlines-protocol/contracts/compare/0.1.3...0.2.0
.. _0.3.0: https://github.com/trustlines-protocol/contracts/compare/0.2.0...0.3.0
.. _0.3.1: https://github.com/trustlines-protocol/contracts/compare/0.3.0...0.3.1
.. _0.3.2: https://github.com/trustlines-protocol/contracts/compare/0.3.1...0.3.2
.. _0.3.3: https://github.com/trustlines-protocol/contracts/compare/0.3.2...0.3.3
.. _0.4.0: https://github.com/trustlines-protocol/contracts/compare/0.3.3...0.4.0
.. _0.5.0: https://github.com/trustlines-protocol/contracts/compare/0.4.0...0.5.0
.. _0.5.1: https://github.com/trustlines-protocol/contracts/compare/0.5.0...0.5.1
.. _0.6.0: https://github.com/trustlines-protocol/contracts/compare/0.5.1...0.6.0
.. _0.6.1: https://github.com/trustlines-protocol/contracts/compare/0.6.0...0.6.1
.. _0.6.2: https://github.com/trustlines-protocol/contracts/compare/0.6.1...0.6.2
.. _0.6.3: https://github.com/trustlines-protocol/contracts/compare/0.6.2...0.6.3
.. _0.7.0: https://github.com/trustlines-protocol/contracts/compare/0.6.3...0.7.0
.. _0.8.0: https://github.com/trustlines-protocol/contracts/compare/0.7.0...0.8.0
.. _0.9.0: https://github.com/trustlines-protocol/contracts/compare/0.8.0...0.9.0
.. _0.9.1: https://github.com/trustlines-protocol/contracts/compare/0.9.0...0.9.1
.. _0.9.2: https://github.com/trustlines-protocol/contracts/compare/0.9.1...0.9.2
.. _0.9.3: https://github.com/trustlines-protocol/contracts/compare/0.9.2...0.9.3
.. _0.10.0: https://github.com/trustlines-protocol/contracts/compare/0.9.3...0.10.0
.. _0.10.1: https://github.com/trustlines-protocol/contracts/compare/0.10.0...0.10.1
.. _1.0.0: https://github.com/trustlines-protocol/contracts/compare/0.10.1...1.0.0
.. _1.1.0: https://github.com/trustlines-protocol/contracts/compare/1.0.0...1.1.0
.. _1.1.1: https://github.com/trustlines-protocol/contracts/compare/1.1.0...1.1.1
.. _1.1.2: https://github.com/trustlines-protocol/contracts/compare/1.1.1...1.1.2
.. _1.1.3: https://github.com/trustlines-protocol/contracts/compare/1.1.2...1.1.3
.. _1.1.4: https://github.com/trustlines-protocol/contracts/compare/1.1.3...1.1.4
.. _1.1.5: https://github.com/trustlines-protocol/contracts/compare/1.1.4...1.1.5
.. _1.1.6: https://github.com/trustlines-protocol/contracts/compare/1.1.5...1.1.6
.. _1.1.7: https://github.com/trustlines-protocol/contracts/compare/1.1.6...1.1.7
.. _next: https://github.com/trustlines-protocol/contracts/compare/1.1.6...master
