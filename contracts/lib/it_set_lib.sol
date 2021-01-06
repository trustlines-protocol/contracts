pragma solidity ^0.8.0;

/**
@dev Library for a Set that can be iterated over
*/
library ItSet {
    struct SetEntry {
        uint256 index; // index of the entry, starting at 1
    }

    struct AddressSet {
        mapping(address => SetEntry) addressToEntry;
        address[] list;
    }

    function insert(AddressSet storage self, address address_) internal {
        SetEntry storage entry = self.addressToEntry[address_];
        if (entry.index == 0) {
            entry.index = self.list.length + 1;
            self.list.push(address_);
        }
    }

    function contains(AddressSet storage self, address address_)
        internal
        view
        returns (bool)
    {
        return self.addressToEntry[address_].index > 0;
    }

    function remove(AddressSet storage self, address address_) internal {
        SetEntry storage entry = self.addressToEntry[address_];
        if (entry.index > 0) {
            // remove from list
            address lastAddress = self.list[self.list.length - 1];
            self.list[entry.index - 1] = lastAddress;
            self.list.pop();
            // update entries
            self.addressToEntry[lastAddress].index = entry.index;
            entry.index = 0;
        }
    }

    function size(AddressSet storage self) internal view returns (uint256) {
        return self.list.length;
    }
}

// SPDX-License-Identifier: MIT
