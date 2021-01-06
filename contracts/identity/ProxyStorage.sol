pragma solidity ^0.8.0;

// Contract used to synchronize storage layout between Identity.sol and Proxy.sol
// Required since we use delegateCall in IdentityProxy to call the implementation of Identity
contract ProxyStorage {
    address public implementation;

    event ImplementationChange(address implementation);
}

// SPDX-License-Identifier: MIT
