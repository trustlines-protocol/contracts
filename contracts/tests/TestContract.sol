pragma solidity ^0.8.0;

import "../currency-network/DebtTracking.sol";

// Test contract used for testing identity contract meta transaction features
contract TestContract is DebtTracking {
    uint256 public testPublicValue = 123456;

    event TestEvent(address from, uint256 value, bytes data, int256 argument);

    constructor() payable {}

    function increaseDebt(address creditor, uint256 value) external override {
        // solium-disable-previous-line no-empty-blocks
    }

    function getDebt(address, address) public pure override returns (int256) {
        return 0;
    }

    function testFunction(int256 argument) public payable {
        address from = msg.sender;
        uint256 value = msg.value;
        bytes memory data = msg.data;
        emit TestEvent(from, value, data, argument);
    }

    function fails() public pure {
        revert("This will just always fail");
    }
}

// SPDX-License-Identifier: MIT
