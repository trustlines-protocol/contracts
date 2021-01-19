pragma solidity ^0.8.0;

import "../lib/it_set_lib.sol";

contract DebtTracking {
    // mapping of a pair of user to the signed debt in the point of view of the lowest address
    mapping(bytes32 => int256) public debt;

    using ItSet for ItSet.AddressSet;
    // list of all debtors of given creditor
    mapping(address => ItSet.AddressSet) internal debtorsOfGivenAddress;
    // list of all debtors of the system
    ItSet.AddressSet internal allDebtors;

    event DebtUpdate(address _debtor, address _creditor, int256 _newDebt);

    /**
     * @notice Used to increase the debt tracked by the currency network of msg.sender towards creditor address
     * @param creditor The address towards which msg.sender increases its debt
     * @param value The value to increase the debt by
     */
    function increaseDebt(address creditor, uint256 value) external virtual {
        int256 intValue = int256(value);
        require(
            uint256(intValue) == value,
            "Value overflow, cannot be cast to int"
        );
        _addToDebt(msg.sender, creditor, intValue);
    }

    /**
     * @notice Get the debt owed by debtor to creditor, may be negative if creditor owes debtor
     * @param debtor The address of which we query the debt
     * @param creditor The address towards which the debtor owes money
     * @return the debt of the debtor to the creditor, equal to the opposite of the debt of the creditor to the debtor
     */
    function getDebt(address debtor, address creditor)
        public
        view
        virtual
        returns (int256)
    {
        if (debtor < creditor) {
            return debt[uniqueIdentifier(debtor, creditor)];
        } else {
            return -debt[uniqueIdentifier(debtor, creditor)];
        }
    }

    /**
     * @notice returns the list of all the debtors,
     * That is a list of all the addresses that currently have a debt (positive or negative)
     **/
    function getAllDebtors() public view returns (address[] memory) {
        return allDebtors.list;
    }

    /**
     * @notice returns the list of debtors of a user
     * That is the list of addresses towards with the user has a debt (positive or negative)
     **/
    function getDebtorsOfUser(address _user)
        public
        view
        returns (address[] memory)
    {
        return debtorsOfGivenAddress[_user].list;
    }

    function _reduceDebt(
        address debtor,
        address creditor,
        uint256 value
    ) internal {
        int256 intValue = int256(value);
        require(
            uint256(intValue) == value,
            "Value overflow, cannot be cast to int"
        );
        _addToDebt(debtor, creditor, -intValue);
    }

    function _addToDebt(
        address debtor,
        address creditor,
        int256 value
    ) internal {
        int256 oldDebt = debt[uniqueIdentifier(debtor, creditor)];
        int256 newDebt;

        if (debtor < creditor) {
            newDebt = oldDebt + value;
            checkIsNotMinInt256(newDebt);
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, newDebt);
        } else {
            newDebt = oldDebt + -value;
            checkIsNotMinInt256(newDebt);
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, -newDebt);
        }
        if (newDebt != 0) {
            addToDebtors(debtor, creditor);
        } else {
            removeFromDebtors(debtor, creditor);
        }
    }

    function checkIsNotMinInt256(int256 a) internal pure {
        require(
            a != type(int256).min,
            "Prevent using value for minus overflow."
        );
    }

    function uniqueIdentifier(address _a, address _b)
        internal
        pure
        virtual
        returns (bytes32)
    {
        require(_a != _b, "Unique identifiers require different addresses");
        if (_a < _b) {
            return keccak256(abi.encodePacked(_a, _b));
        } else if (_a > _b) {
            return keccak256(abi.encodePacked(_b, _a));
        } else {
            revert("Unreachable");
        }
    }

    function addToDebtors(address _a, address _b) internal {
        allDebtors.insert(_a);
        allDebtors.insert(_b);
        debtorsOfGivenAddress[_a].insert(_b);
        debtorsOfGivenAddress[_b].insert(_a);
    }

    function removeFromDebtors(address _a, address _b) internal {
        debtorsOfGivenAddress[_a].remove(_b);
        debtorsOfGivenAddress[_b].remove(_a);
        if (debtorsOfGivenAddress[_a].size() == 0) {
            allDebtors.remove(_a);
        }
        if (debtorsOfGivenAddress[_b].size() == 0) {
            allDebtors.remove(_b);
        }
    }
}

// SPDX-License-Identifier: MIT
