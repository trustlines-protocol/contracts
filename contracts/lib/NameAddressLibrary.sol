/*
This library serves as storage for the name address mappings of TLToken Names and their addresses
*/
pragma solidity ^0.4.0;


library NameAddressLibrary {
    struct NameAddressMapEntry {
        address tlTokenAddress;
        uint idx;
    }

    struct NameAddressMap {
        mapping (string => NameAddressMapEntry) entries;
        string[] keys;
    }

    function set(NameAddressMap storage self, string name, address addr) internal returns (bool){
        var entry = self.entries[name];
        if (entry.idx == 0) {
            entry.idx = self.keys.length + 1;
            entry.tlTokenAddress = addr;
            self.keys.push(name);
            return true;
        }
        return false;
    }

    function get(NameAddressMap storage self, string name) internal constant returns (address){
        return self.entries[name].tlTokenAddress;
    }

    function contains(NameAddressMap storage self, string name) internal constant returns (bool){
        return self.entries[name].idx > 0;
    }

    function remove(NameAddressMap storage self, string name) internal returns (bool){
        var entry = self.entries[name];
        if (entry.idx > 0) {
            var otherkey = self.keys[self.keys.length - 1];
            self.keys[entry.idx - 1] = otherkey;
            self.keys.length -= 1;

            self.entries[otherkey].idx = entry.idx;
            entry.idx = 0;
            entry.tlTokenAddress = 0;
            return true;
        }
        return false;
    }

    function size(NameAddressMap storage self) internal constant returns (uint) {
        return self.keys.length;
    }

    function index(NameAddressMap storage self, uint idx) internal constant returns (string) {
        return self.keys[idx];
    }

    function getAllTLTokens(NameAddressMap storage self) internal constant returns (address[]){
        address[] memory tlTokens = new address[](self.keys.length);
        for (uint i = 0; i < self.keys.length; i++) {
            tlTokens[i] = self.entries[self.keys[i]].tlTokenAddress;
        }
        return tlTokens;
    }

    function getAllNames(NameAddressMap storage self) internal constant returns (string[]){
        return self.keys;
    }
}
