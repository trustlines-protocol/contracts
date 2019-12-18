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


}
