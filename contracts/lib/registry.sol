pragma solidity ^0.4.11;


import "./NameAddressLibrary.sol";


/*
This contract serves as Registry contract for Name to Address mappings of TLTokens
*/
contract Registry {
    using NameAddressLibrary for NameAddressLibrary.NameAddressMap;
    NameAddressLibrary.NameAddressMap registry;

    event TLTokenNameRegistered(string name, address tltokenAddress);
    event TLTokenNameDeRegistered(string name);

    function register(string name, address tlToken) external returns (bool success) {
        success = false;

        //if(!registry.contains(name)){
        //    success = registry.set(name, tlToken);
        //    TLTokenNameRegistered(name, tlToken);
        // }
    }

    function getTLTokenAddress(string name) constant returns (address) {
        return registry.get(name);
    }

    function contains(string name) constant returns (bool) {
        return registry.contains(name);
    }

    function unregister(string name) returns (bool success) {
        success = registry.remove(name);
        TLTokenNameDeRegistered(name);
    }

    function size() constant returns (uint) {
        return registry.size();
    }

    function index(uint idx) constant returns (string) {
        return registry.index(idx);
    }

    function getAllTLTokens() constant returns (address[]) {
        address[] memory tlTokens = new address[](registry.keys.length);
        for (uint i = 0; i < registry.keys.length; i++) {
            tlTokens[i] = registry.entries[registry.keys[i]].tlTokenAddress;
        }
        return tlTokens;
    }

}
