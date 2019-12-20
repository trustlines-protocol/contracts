pragma solidity ^0.5.8;


contract CurrencyNetworkSafeMath {

    function safeSub(uint64 a, uint64 b)
        internal
        pure
        returns (uint64)
    {
        require(b <= a, "SafeMath: Sub Overflow");
        return a - b;
    }

    function safeAdd(uint64 a, uint64 b)
        internal
        pure
        returns (uint64)
    {
        uint64 c = a + b;
        require(c >= a, "SafeMath: Add Overflow");
        return c;
    }

    function safeSubInt(int72 a, uint64 b)
        internal
        pure
        returns (int72)
    {
        int72 c = a - b;
        require(c <= a, "SafeMath: SubInt Overflow");
        return c;
    }

    function safeMinus(int72 a)
        internal
        pure
        returns (int72)
    {
        if (a == 0) {
            return a;
        }
        int72 c = -a;
        require(c != a, "SafeMath: Minus Overflow");
        return c;
    }

    function safeMinusInt256(int a)
        internal
        pure
        returns (int)
    {
        if (a == 0) {
            return a;
        }
        int c = -a;
        require(c != a, "SafeMath: Minus Overflow");
        return c;
    }

    function safeSumInt256(int a, int b) internal pure returns (int sum) {
        sum = a + b;
        if (a > 0 && b > 0) {
            require(sum > 0, "Overflow error.");
        }
        if (a < 0 && b < 0) {
            require(sum < 0, "Underflow error.");
        }
    }

    function checkIsNotMinInt256(int a) internal pure returns (bool) {
        require(a != - 2 ** 255, "Prevent using value for minus overflow.");
    }
}
