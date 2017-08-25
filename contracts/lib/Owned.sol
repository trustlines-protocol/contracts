pragma solidity ^0.4.11;

contract Owned {
    address public owner;
    address public admin;

    modifier onlyOwner() {
        require (isOwner(msg.sender));
        _;
    }

    modifier ifOwner(address _sender) {
        if (isOwner(_sender)) {
            _;
        }
    }

    modifier onlyAdmin() {
        require (isAdmin(msg.sender));
        _;
    }

    modifier ifAdmin(address _sender) {
        if (isAdmin(_sender)) {
            _;
        }
    }

    function Owned(address _admin) {
        owner = msg.sender;
        admin = _admin;
    }

    function isOwner(address _addr) public returns (bool) {
        return owner == _addr;
    }

    function isAdmin(address _addr) public returns (bool) {
        return admin == _addr;
    }

    function transfer(address _owner) onlyAdmin {
        owner = _owner;
    }
}
