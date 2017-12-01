pragma solidity ^0.4.11;


/**
 * Math operations with safety checks
 */
library SafeMath {

    function mul(uint a, uint b) internal returns (uint) {
        uint c = a * b;
        require(a == 0 || c / a == b);
        return c;
    }

    function mul16(uint16 a, uint16 b) internal returns (uint16) {
        uint16 c = a * b;
        require(a == 0 || c / a == b);
        return c;
    }

    function mul32(uint32 a, uint32 b) internal returns (uint32) {
        uint32 c = a * b;
        require(a == 0 || c / a == b);
        return c;
    }

    function mul(int a, int b) internal returns (int) {
        int c = a * b;
        require(a == 0 || c / a == b);
        return c;
    }

    function div(uint a, uint b) internal returns (uint) {
        require(b > 0);
        uint c = a / b;
        require(a == b * c + a % b);
        return c;
    }

    function div32(uint32 a, uint16 b) internal returns (uint32) {
        require(b > 0);
        uint32 c = a / b;
        require(a == b * c + a % b);
        return c;
    }

    function div3216(uint32 a, uint16 b) internal returns (uint16) {
        require(b > 0);
        uint16 c = uint16(a) / b;
        require(a == b * c + a % b);
        return c;
    }

    function div6416(int64 a, uint16 b) internal returns (uint16) {
        require(b > 0);
        uint16 c = uint16(a) / b;
        require(a == b * c + a % b);
        return c;
    }

    function div(int a, int b) internal returns (int) {
        require(b > 0);
        int c = a / b;
        require(a == b * c + a % b);
        return c;
    }

    function sub(uint a, uint b) internal returns (uint) {
        require(b <= a);
        return a - b;
    }

    function sub16(uint16 a, uint16 b) internal returns (uint16) {
        require(b <= a);
        return a - b;
    }

    function sub32(uint32 a, uint16 b) internal returns (uint32) {
        require(b <= a);
        return a - b;
    }

    function sub(int a, int b) internal returns (int) {
        int c = a - b;
        require(c + b == a);
        return c;
    }

    function sub64(int64 a, int64 b) internal returns (int64) {
        int64 c = a - b;
        require(c + b == a);
        return c;
    }

    function add(uint a, uint b) internal returns (uint) {
        uint c = a + b;
        require(c >= a);
        return c;
    }

    function add16(uint16 a, uint16 b) internal returns (uint16) {
        uint16 c = a + b;
        require(c >= a);
        return c;
    }

    function add64(int64 a, int64 b) internal returns (int64) {
        int64 c = a + b;
        require(c >= a);
        return c;
    }

    function add(int a, int b) internal returns (int) {
        int c = a + b;
        require(c >= a);
        return c;
    }

    function max64(uint64 a, uint64 b) internal constant returns (uint64) {
        return a >= b ? a : b;
    }

    function min64(uint64 a, uint64 b) internal constant returns (uint64) {
        return a < b ? a : b;
    }

    function max256(uint256 a, uint256 b) internal constant returns (uint256) {
        return a >= b ? a : b;
    }

    function min256(uint256 a, uint256 b) internal constant returns (uint256) {
        return a < b ? a : b;
    }

}
