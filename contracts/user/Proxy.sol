pragma solidity ^0.4.0;

import "../lib/Owned.sol";
import "../lib/ERC20.sol";
import "../ICurrencyNetwork.sol";

contract Proxy is ERC20, Owned, ICurrencyNetwork {

    address destination;

    event Forwarded (address indexed destination, string value, address sender, address owner);

    event Received (address indexed sender, uint value);

    function Proxy(address _destination) {
        destination = _destination;
    }

    function() payable {Received(msg.sender, msg.value);}

    function updateCreditline(address _debtor, uint32 _value) external {
        ICurrencyNetwork(destination).updateCreditline(_debtor, _value);
    }

    function acceptCreditline(address _debtor, uint32 _value) external returns (bool) {
        return ICurrencyNetwork(destination).acceptCreditline(_debtor, _value);
    }

    function transfer(address to, uint value) public {
        ERC20(destination).transfer(to, value);
    }

    function transferFrom(address from, address to, uint value) public {
        ERC20(destination).transferFrom(from, to, value);
    }

    function approve(address spender, uint value) public {
        ERC20(destination).approve(spender, value);
    }

    function balanceOf(address who) public constant returns (uint) {
        return ERC20(destination).balanceOf(who);
    }

    function allowance(address owner, address spender) public constant returns (uint) {
        return ERC20(destination).allowance(owner, spender);
    }

}