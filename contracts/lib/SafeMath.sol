pragma solidity ^0.4.0;


/**
 * Math operations with safety checks
 */
library SafeMath {
  
  function mul(uint a, uint b) internal returns (uint) {
    uint c = a * b;
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

  function div24(uint24 a, uint16 b) internal returns (uint24) {
    assert(b > 0);
    uint24 c = a / b;
    assert(a == b * c + a % b);
    return c;
  }

  function div4824(int48 a, uint24 b) internal returns (uint24) {
    assert(b > 0);
    uint24 c = uint24(a) / b;
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

  function sub24(uint24 a, uint24 b) internal returns (uint24) {
    assert(b <= a);
    return a - b;
  }

  function sub(int a, int b) internal returns (int) {
    int c = a - b;
    assert(c + b == a);
    return c;
  }

  function sub48(int48 a, int48 b) internal returns (int48) {
    int48 c = a - b;
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

  function add48(int48 a, int48 b) internal returns (int48) {
    int48 c = a + b;
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
