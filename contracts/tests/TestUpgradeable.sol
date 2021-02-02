pragma solidity ^0.8.0;

// Test contract used for testing upgradeability with proxy and beacon
contract TestUpgradeable {
    int256 public initializedValue;
    int256 public testValue;

    function init(int256 value) public {
        initializedValue = value;
    }

    function setTestValue(int256 _testValue) public payable {
        testValue = _testValue;
    }

    function version() public pure returns (int256) {
        return 1;
    }

    function admin() external view returns (address) {
        // This is a test function that clashes with the `admin` function of the proxy
        return address(this);
    }
}

// SPDX-License-Identifier: MIT
