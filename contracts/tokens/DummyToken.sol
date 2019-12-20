pragma solidity ^0.5.8;

import "./../lib/SafeMath.sol";
import "./../tokens/StandardToken.sol";


contract DummyToken is StandardToken, SafeMath {
    string public name;
    string public symbol;
    uint public decimals;

    constructor(
        string memory _name,
        string memory _symbol,
        uint _decimals,
        uint _totalSupply
    )
        public
    {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _totalSupply;
        balances[msg.sender] = _totalSupply;
    }

    function setBalance(address _target, uint _value)
        public
    {
        uint currBalance = balanceOf(_target);
        if (_value < currBalance) {
            totalSupply = safeSub(totalSupply, safeSub(currBalance, _value));
        } else {
            totalSupply = safeAdd(totalSupply, safeSub(_value, currBalance));
        }
        balances[_target] = _value;
    }
}
