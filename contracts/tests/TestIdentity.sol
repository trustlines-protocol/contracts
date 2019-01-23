pragma solidity ^0.4.25;

/*
  The sole purpose of this file is to be able to test the internal functions of the identity contract
*/


import "../Identity.sol";


contract TestIdentity is Identity {

    function testIsSignatureFromOwner(bytes32 _data, bytes _signature) public view returns (bool) {
        return isSignatureFromOwner(_data, _signature);
    }
}
