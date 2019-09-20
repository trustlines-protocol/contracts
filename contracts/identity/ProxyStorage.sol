pragma solidity ^0.5.8;


// Contract used to synchronize storage layout between Identity.sol and IdentityProxy.sol
// Required since we use delegateCall in IdentityProxy to call the implementation of Identity
contract ProxyStorage {

    address public identityImplementation;
    uint public implementationVersion = 1;

}
