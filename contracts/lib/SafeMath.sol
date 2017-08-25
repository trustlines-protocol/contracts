pragma solidity ^0.4.11;


/**
 * Math operations with safety checks
 */
library SafeMath {
  
  function mul(uint a, uint b) internal returns (uint) {
    uint c = a * b;
    assert(a == 0 || c / a == b);
    return c;
  }

  function mul16(uint16 a, uint16 b) internal returns (uint16) {
    uint16 c = a * b;
    assert(a == 0 || c / a == b);
    return c;
  }

  function mul32(uint32 a, uint32 b) internal returns (uint32) {
    uint32 c = a * b;
    assert(a == 0 || c / a == b);
    return c;
  }

  function mul(int a, int b) internal returns (int) {
    int c = a * b;
    assert(a == 0 || c / a == b);
    return c;
  }

  function div(uint a, uint b) internal returns (uint) {
    assert(b > 0);
    uint c = a / b;
    assert(a == b * c + a % b);
    return c;
  }

  function div32(uint32 a, uint16 b) internal returns (uint32) {
    assert(b > 0);
    uint32 c = a / b;
    assert(a == b * c + a % b);
    return c;
  }

  function div3216(uint32 a, uint16 b) internal returns (uint16) {
    assert(b > 0);
    uint16 c = uint16(a) / b;
    assert(a == b * c + a % b);
    return c;
  }

  function div6416(int64 a, uint16 b) internal returns (uint16) {
    assert(b > 0);
    uint16 c = uint16(a) / b;
    assert(a == b * c + a % b);
    return c;
  }

  function div(int a, int b) internal returns (int) {
    assert(b > 0);
    int c = a / b;
    assert(a == b * c + a % b);
    return c;
  }

  function sub(uint a, uint b) internal returns (uint) {
    assert(b <= a);
    return a - b;
  }
  
  function sub16(uint16 a, uint16 b) internal returns (uint16) {
    assert(b <= a);
    return a - b;
  }

  function sub32(uint32 a, uint16 b) internal returns (uint32) {
    assert(b <= a);
    return a - b;
  }

  function sub(int a, int b) internal returns (int) {
    int c = a - b;
    assert(c + b == a);
    return c;
  }

  function sub64(int64 a, int64 b) internal returns (int64) {
    int64 c = a - b;
    assert(c + b == a);
    return c;
  }

  function add(uint a, uint b) internal returns (uint) {
    uint c = a + b;
    assert(c >= a);
    return c;
  }

  function add16(uint16 a, uint16 b) internal returns (uint16) {
    uint16 c = a + b;
    assert(c >= a);
    return c;
  }

  function add64(int64 a, int64 b) internal returns (int64) {
    int64 c = a + b;
    assert(c >= a);
    return c;
  }

  function add(int a, int b) internal returns (int) {
    int c = a + b;
    assert(c >= a);
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

  function assert(bool assertion) internal {
    if (!assertion) {
      throw;
    }
  }
  
}
