pragma solidity ^0.6.5;

/*
 * Contract that is working with ERC223 tokens
 */

interface ContractReceiver {
    function tokenFallback(
        address _from,
        uint256 _value,
        bytes calldata _data
    ) external;
}
