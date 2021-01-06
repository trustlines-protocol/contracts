pragma solidity ^0.8.0;

import "./../tokens/StandardToken.sol";

contract DummyToken is StandardToken {
    string public name;
    string public symbol;
    uint256 public decimals;

    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _decimals,
        uint256 _totalSupply
    ) {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _totalSupply;
        balances[msg.sender] = _totalSupply;
    }

    function setBalance(address _target, uint256 _value) public {
        uint256 currBalance = balanceOf(_target);
        if (_value < currBalance) {
            totalSupply = totalSupply - (currBalance - _value);
        } else {
            totalSupply = totalSupply + (_value - currBalance);
        }
        balances[_target] = _value;
    }
}

// SPDX-License-Identifier: MIT
