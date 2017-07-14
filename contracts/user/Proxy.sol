pragma solidity ^0.4.0;

import "../lib/Owned.sol";
import "../lib/ERC20.sol";
import "../ICurrencyNetwork.sol";

contract Proxy is ERC20, Owned, ICurrencyNetwork {

    address destination;

    event Forwarded (address indexed destination, string value, address sender, address owner);

    event Received (address indexed sender, uint value);

    function() payable {Received(msg.sender, msg.value);}

    function Proxy(address _destination) {
        destination = _destination;
    }

    function balanceOf(address who) constant returns (uint) {
        return ERC20(destination).balanceOf(who);
    }

    function transfer(address to, uint value)  {
        ERC20(destination).transfer(to, value);
    }

    function allowance(address owner, address spender) constant returns (uint) {
        return ERC20(destination).allowance(owner, spender);
    }

    function transferFrom(address from, address to, uint value)  {
        ERC20(destination).transferFrom(from, to, value);
    }

    function approve(address spender, uint value) {
        ERC20(destination).approve(spender, value);
    }

    function updateCreditline(address _debtor, uint32 _value) {
        ICurrencyNetwork(destination).updateCreditline(_debtor, _value);
    }

    function acceptCreditline(address _debtor, uint32 _value) returns (bool) {
        return ICurrencyNetwork(destination).acceptCreditline(_debtor, _value);
    }

}