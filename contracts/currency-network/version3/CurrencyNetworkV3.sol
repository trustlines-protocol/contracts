pragma solidity ^0.8.0;

import "../version2/CurrencyNetworkV2.sol";
import "../DebtTracking.sol";

/**
 * CurrencyNetwork
 *
 * Extends basic currency networks to add debt tracking, debit transfer, and onboarding.
 *
 **/
contract CurrencyNetworkV3 is CurrencyNetworkV2 {

    /**
     * A small trick to make the contracts compatible with GnosisSafe
     * delegate payments.
     *
     * @param _creditor The address towards which msg.sender increases its debt
     * @param _value The value to increase the debt by
     **/
    function transfer(address _creditor, uint256 _value) external {
        DebtTracking debtContract = DebtTracking(address(this));

        debtContract.increaseDebt(_creditor, _value);
    }
}

// SPDX-License-Identifier: MIT
