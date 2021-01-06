pragma solidity ^0.8.0;

import "./Token.sol";

contract StandardToken is Token {
    function transfer(address _to, uint256 _value)
        public
        override
        returns (bool)
    {
        //Default assumes totalSupply can't be over max (2^256 - 1).
        if (
            balances[msg.sender] >= _value &&
            balances[_to] + _value >= balances[_to]
        ) {
            balances[msg.sender] -= _value;
            balances[_to] += _value;
            emit Transfer(msg.sender, _to, _value);
            return true;
        } else {
            return false;
        }
    }

    function transferFrom(
        address _from,
        address _to,
        uint256 _value
    ) public override returns (bool) {
        if (
            balances[_from] >= _value &&
            allowed[_from][msg.sender] >= _value &&
            balances[_to] + _value >= balances[_to]
        ) {
            balances[_to] += _value;
            balances[_from] -= _value;
            allowed[_from][msg.sender] -= _value;
            emit Transfer(_from, _to, _value);
            return true;
        } else {
            return false;
        }
    }

    function balanceOf(address _owner) public view override returns (uint256) {
        return balances[_owner];
    }

    function approve(address _spender, uint256 _value)
        public
        override
        returns (bool)
    {
        allowed[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);
        return true;
    }

    function allowance(address _owner, address _spender)
        public
        view
        override
        returns (uint256)
    {
        return allowed[_owner][_spender];
    }

    mapping(address => uint256) balances;
    mapping(address => mapping(address => uint256)) allowed;
    uint256 public totalSupply;
}

// SPDX-License-Identifier: MIT
