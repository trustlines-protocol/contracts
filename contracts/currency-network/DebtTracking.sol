pragma solidity ^0.8.0;

import "./CurrencyNetworkSafeMath.sol";

contract DebtTracking is CurrencyNetworkSafeMath {
    // mapping of a pair of user to the signed debt in the point of view of the lowest address
    mapping(bytes32 => int256) public debt;

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
            return safeMinusInt256(debt[uniqueIdentifier(debtor, creditor)]);
        }
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
        _addToDebt(debtor, creditor, safeMinusInt256(intValue));
    }

    function _addToDebt(
        address debtor,
        address creditor,
        int256 value
    ) internal {
        int256 oldDebt = debt[uniqueIdentifier(debtor, creditor)];
        if (debtor < creditor) {
            int256 newDebt = safeSumInt256(oldDebt, value);
            checkIsNotMinInt256(newDebt);
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, newDebt);
        } else {
            int256 newDebt = safeSumInt256(oldDebt, safeMinusInt256(value));
            checkIsNotMinInt256(newDebt);
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, -newDebt);
        }
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
}

// SPDX-License-Identifier: MIT
