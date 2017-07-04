pragma solidity ^0.4.0;

import "../lib/Owned.sol";
import "../lib/ERC20.sol";

contract Proxy is ERC20, Owned {

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
        return ERC20(destination).transfer(to, value);
    }

    function allowance(address owner, address spender) constant returns (uint) {
        return ERC20(destination).allowance(owner, spender);
    }

    function transferFrom(address from, address to, uint value)  {
        return ERC20(destination).transferFrom(from, to, value);
    }

    function approve(address spender, uint value) {
        return ERC20(destination).approve(spender, value);
    }

}