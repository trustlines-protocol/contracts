pragma solidity ^0.4.25;

/*
  The sole purpose of this file is to be able to test the internal functions of the identity contract
*/


import "../Identity.sol";


contract TestIdentity is Identity {

    function testIsSignatureValid(bytes32 _data, bytes _signature) public view returns (bool) {
        return isSignatureValid(_data, _signature);
    }

    function testTransactionHash(
        address from,
        address to,
        uint256 value,
        bytes data,
        uint256 nonce,
        bytes extraHash
    )
        public
        view
        returns (bytes32)
    {
        return transactionHash(
            from,
            to,
            value,
            data,
            nonce,
            extraHash
        );
    }
}
