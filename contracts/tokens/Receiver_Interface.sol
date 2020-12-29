pragma solidity ^0.8.0;

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

// SPDX-License-Identifier: MIT
