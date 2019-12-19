pragma solidity ^0.5.8;

import "./CurrencyNetworkSafeMath.sol";


contract DebtTracking is CurrencyNetworkSafeMath {

    // mapping of a pair of user to the signed debt in the point of view of the lowest address
    mapping (bytes32 => int72) public debt;

    event DebtUpdate(address _debtor, address _creditor, int72 _newDebt);

    /**
     * @notice Used to increase the debt tracked by the currency network of msg.sender towards creditor address
     * @param creditor The address towards which msg.sender increases its debt
     * @param value The value to increase the debt by
     */
    function increaseDebt(address creditor, uint64 value) external {
        _addToDebt(msg.sender, creditor, value);
    }

    /**
     * @notice Get the debt owed by debtor to creditor, may be negative if creditor owes debtor
     * @param debtor The address of which we query the debt
     * @param creditor The address towards which the debtor owes money
     * @return the debt of the debtor to the creditor, equal to the opposite of the debt of the creditor to the debtor
     */
    function getDebt(address debtor, address creditor) public view returns (int80) {
        if (debtor < creditor) {
            return debt[uniqueIdentifier(debtor, creditor)];
        } else {
            // We need to explicitly cast to int80 to be able to safely oppose the int72 debt
            return - int80(debt[uniqueIdentifier(debtor, creditor)]);
        }
    }

    function _reduceDebt(address debtor, address creditor, uint64 value) internal {
        _addToDebt(debtor, creditor, - int72(value));
    }

    function _addToDebt(address debtor, address creditor, int72 value) internal {
        int72 oldDebt = debt[uniqueIdentifier(debtor, creditor)];
        if (debtor < creditor) {
            int72 newDebt = safeSumInt72(oldDebt, value);
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, newDebt);
        } else {
            int72 newDebt = safeSumInt72(oldDebt, safeMinus(value));
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, safeMinus(newDebt));
        }
    }

    function uniqueIdentifier(address _a, address _b) internal pure returns (bytes32) {
        require(_a != _b, "Unique identifiers require different addresses");
        if (_a < _b) {
            return keccak256(abi.encodePacked(_a, _b));
        } else if (_a > _b) {
            return keccak256(abi.encodePacked(_b, _a));
        }
    }
}
