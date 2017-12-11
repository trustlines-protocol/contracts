pragma solidity ^0.4.9;


import "./Receiver_Interface.sol";
import "./ERC223_Interface.sol";


/**
* ERC23 token original by Dexaran
*
* https://github.com/Dexaran/ERC23-tokens
*/


/* https://github.com/LykkeCity/EthereumApiDotNetCore/blob/master/src/ContractBuilder/contracts/token/SafeMath.sol */
contract SafeMath {

    uint256 constant public MAX_UINT256 =
    0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF;

    function safeAdd(uint256 x, uint256 y) constant internal returns (uint256 z) {
        require(x <= MAX_UINT256 - y);

        return x + y;
    }

    function safeSub(uint256 x, uint256 y) constant internal returns (uint256 z) {
        require(x >= y);
        return x - y;
    }

    function safeMul(uint256 x, uint256 y) constant internal returns (uint256 z) {
        if (y == 0)
            return 0;
        require(x <= MAX_UINT256 / y);
        return x * y;
    }
}


contract ERC223Token is ERC223, SafeMath {

    mapping (address => uint) balances;
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;

    // Function to access name of token .
    function name() public constant returns (string _name) {
        return name;
    }

    // Function to access symbol of token .
    function symbol() public constant returns (string _symbol) {
        return symbol;
    }

    // Function to access decimals of token .
    function decimals() public constant returns (uint8 _decimals) {
        return decimals;
    }

    // Function to access total supply of tokens .
    function totalSupply() public constant returns (uint256 _totalSupply) {
        return totalSupply;
    }

    // Function that is called when a user or another contract wants to transfer funds .
    function transfer(address _to, uint _value, bytes _data) public returns (bool success) {

        if (isContract(_to)) {
            return transferToContract(_to, _value, _data);
        } else {
            return transferToAddress(_to, _value, _data);
        }
    }

    // Standard function transfer similar to ERC20 transfer with no _data .
    // Added due to backwards compatibility reasons .
    function transfer(address _to, uint _value) public returns (bool success) {

        // standard function transfer similar to ERC20 transfer with no _data
        // added due to backwards compatibility reasons
        bytes memory empty;
        if (isContract(_to)) {
            return transferToContract(_to, _value, empty);
        } else {
            return transferToAddress(_to, _value, empty);
        }
    }

    function balanceOf(address _owner) public constant returns (uint balance) {
        return balances[_owner];
    }

    // assemble the given address bytecode. If bytecode exists then the _addr is a contract.
    function isContract(address _addr) private returns (bool isContract) {
        uint length;
        assembly {
            //retrieve the size of the code on target address, this needs assembly
            length := extcodesize(_addr)
        }
        if (length > 0) {
            return true;
        } else {
            return false;
        }
    }

    // function that is called when transaction target is an address
    function transferToAddress(address _to, uint _value, bytes _data) private returns (bool success) {
        require(balanceOf(msg.sender) >= _value);
        balances[msg.sender] = safeSub(balanceOf(msg.sender), _value);
        balances[_to] = safeAdd(balanceOf(_to), _value);

        Transfer(
            msg.sender,
            _to,
            _value,
            _data);

        return true;
    }

    // function that is called when transaction target is a contract
    function transferToContract(address _to, uint _value, bytes _data) private returns (bool success) {
        require(balanceOf(msg.sender) >= _value);
        balances[msg.sender] = safeSub(balanceOf(msg.sender), _value);
        balances[_to] = safeAdd(balanceOf(_to), _value);
        ContractReceiver receiver = ContractReceiver(_to);
        receiver.tokenFallback(msg.sender, _value, _data);

        Transfer(
            msg.sender,
            _to,
            _value,
            _data);

        return true;
    }

}
