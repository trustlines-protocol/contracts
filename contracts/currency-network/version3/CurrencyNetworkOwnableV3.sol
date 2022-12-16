pragma solidity ^0.8.0;

import "../version2/CurrencyNetworkOwnableV2.sol";


contract CurrencyNetworkOwnableV3 is CurrencyNetworkOwnableV2 {
    /**
     * A small trick to make the contracts compatible with GnosisSafe
     * delegate payments.
     *
     * @param _creditor The address towards which msg.sender increases its debt
     * @param _value The value to increase the debt by
     **/
    function transfer(address _creditor, uint256 _value) external {
        CurrencyNetworkV2(address(this)).increaseDebt(_creditor, _value);
    }
}

// SPDX-License-Identifier: MIT
