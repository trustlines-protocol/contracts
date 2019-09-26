pragma solidity ^0.5.8;


// Contract used to synchronize storage layout between Identity.sol and Proxy.sol
// Required since we use delegateCall in IdentityProxy to call the implementation of Identity
contract ProxyStorage {

    address public implementation;

}
