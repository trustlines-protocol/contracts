pragma solidity ^0.8.0;

import "../currency-network/CurrencyNetworkSafeMath.sol";

contract TestCurrencyNetworkSafeMath is CurrencyNetworkSafeMath {
    function testSafeSub(uint64 a, uint64 b) public pure returns (uint64) {
        return super.safeSub(a, b);
    }

    function testSafeAdd(uint64 a, uint64 b) public pure returns (uint64) {
        return super.safeAdd(a, b);
    }

    function testSafeSubInt(int72 a, uint64 b) public pure returns (int72) {
        return super.safeSubInt(a, b);
    }

    function testSafeMinus(int72 a) public pure returns (int72) {
        return super.safeMinus(a);
    }
}

// SPDX-License-Identifier: MIT
