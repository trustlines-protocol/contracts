## Smart Contract API

This document describes the API for all smart contracts of Trustlines.
These smart contracts consist of the base contracts like `CurrencyNetwork` and supporting contracts like `StableCoinHub`.

The interactions of the contracts are described in a separate document.

## Terminology

As part of the Trustlines protocol, entities are `code-styled` to show that certain functionality and specifications are referenced by this specific term.

The terminology is defined in the glossary in the appendix.

### `CurrencyNetwork.sol`
The main smart contract representing a network of one currency, which is realized as a collection of `Trustlines` between `UserAccounts`.

### prepare

Prepare a path between two UserAccounts, `msg.sender` and `_to`. This path is valid _one day_ after preparation.
The path is calculated by a system of federated relay servers off-chain.

+ Parameters
    + `_to` - address of receiver
    + `_value` - value of transfer
    + `_maxFee` - maximum fee which sender accepts to pay
    + `_path` - array of addresses of Trustlines which have been calculated by the relay server


+ Result on success

  ###### Events

      PathPrepared(address _sender, address _receiver, uint32 _value)

### prepareFrom

Prepare a path between two UserAccounts, `_from` and `_to`. This path is valid _one day_ after preparation.
The path is calculated by a system of federated relay servers off-chain.

+ Parameters
    + `_to` - address of receiver
    + `_value` - value of transfer
    + `_maxFee` - maximum fee which sender accepts to pay
    + `_path` - array of addresses of Trustlines which have been calculated by the relay server


+ Result on success

  ###### Events

      PathPrepared(address _from, address _receiver, uint32 _value)

### cashCheque

Create a `Cheque` which is signed by `UserAccount` `_from` and can be redeemed by `_to`.
The Cheque has an expiry date which is set in `_expiresOn`. These values are hashed and must be signed by `_from`.

+ Parameters
    + `_from` - address of the account able to transfer the tokens
    + `_to` -  address of the recipient
    + `_value` - value of transfer
    + `_expiresOn` - amount of token to be transferred
    + `_signature` - the values _from, _to, _value and _expiresOn signed by _from


+ Result on success

  ###### Events

        Transfer events according to mediatedTransfer(...)
