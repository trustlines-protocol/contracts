pragma solidity ^0.4.0;

/**
@dev Library for a Set that can be iterated over
*/
library ItSet {
    struct SetEntry {
    uint index; // index of the entry, starting at 1
    }

    struct AddressSet {
    mapping (address => SetEntry) addressToEntry;
    address[] list;
    }

    function insert(AddressSet storage self, address address_) internal {
        var entry = self.addressToEntry[address_];
        if (entry.index == 0) {
            entry.index = self.list.length + 1;
            self.list.push(address_);
        }
    }

    function contains(AddressSet storage self, address address_) internal constant returns (bool) {
        return self.addressToEntry[address_].index > 0;
    }

    function remove(AddressSet storage self, address address_) internal {
        var entry = self.addressToEntry[address_];
        if (entry.index > 0) {
            // remove from list
            var last_address = self.list[self.list.length - 1];
            self.list[entry.index - 1] = last_address;
            self.list.length -= 1;
            // update entries
            self.addressToEntry[last_address].index = entry.index;
            entry.index = 0;
        }
    }

    function size(AddressSet storage self) internal constant returns (uint) {
        return self.list.length;
    }
}
