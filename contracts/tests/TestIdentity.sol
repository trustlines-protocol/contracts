pragma solidity ^0.5.8;

/*
  The sole purpose of this file is to be able to test the internal functions of the identity contract
*/


import "../Identity.sol";


contract TestIdentity is Identity {

    function testTransactionHash(
        address from,
        address to,
        uint256 value,
        bytes memory data,
        uint256 nonce,
        bytes memory extraHash
    )
        public
        pure
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
