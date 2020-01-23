pragma solidity ^0.5.8;

/*
  The sole purpose of this file is to be able to test the internal functions of the identity contract
*/


import "../identity/Identity.sol";


contract TestIdentity is Identity {

    function testTransactionHash(
        address from,
        address to,
        uint256 value,
        bytes memory data,
        uint256 baseFee,
        uint256 gasPrice,
        uint256 gasLimit,
        address feeRecipient,
        address currencyNetworkOfFees,
        uint256 nonce,
        uint256 timeLimit,
        uint8 operationType
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
            baseFee,
            gasPrice,
            gasLimit,
            feeRecipient,
            currencyNetworkOfFees,
            nonce,
            timeLimit,
            operationType
        );
    }
}
