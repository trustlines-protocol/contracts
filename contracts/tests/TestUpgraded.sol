pragma solidity ^0.8.0;

// Test contract used for testing upgradeability with proxy and beacon
contract TestUpgraded {
    int256 public initializedValue;
    int256 public testValue;

    function init(int256 value) public {
        initializedValue = value;
    }

    function setTestValue(int256 _testValue) public payable {
        testValue = _testValue;
    }

    function version() public pure returns (int256) {
        return 2;
    }
}

// SPDX-License-Identifier: MIT
