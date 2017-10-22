// TODO check if still used!
pragma solidity ^0.4.11;


contract Owned {

    address public owner;
    address public admin;

    modifier onlyOwnerOrAdmin() {
        require(isOwner(msg.sender) || isAdmin(msg.sender));
        _;
    }

    modifier onlyOwner() {
        require(isOwner(msg.sender));
        _;
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

    function transfer(address _owner) onlyOwnerOrAdmin {
        owner = _owner;
    }
}
