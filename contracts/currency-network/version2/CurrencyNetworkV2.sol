pragma solidity ^0.8.0;

import "../DebtTracking.sol";
import "../Onboarding.sol";
import "./CurrencyNetworkBasicV2.sol";

/**
 * CurrencyNetwork
 *
 * Extends basic currency networks to add debt tracking, debit transfer, and onboarding.
 *
 **/
contract CurrencyNetworkV2 is CurrencyNetworkBasicV2, DebtTracking, Onboarding {
    /**
     * @notice send `_value` along `_path`
     * sender needs to have a debt towards receiver of at least `_value`
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the receiver wants to pay
     * @param _path Path of transfer starting with debtor and ending with creditor (msg.sender)
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function debitTransfer(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    ) external {
        address from = _path[0];
        address to = _path[_path.length - 1];
        require(
            to == msg.sender,
            "The transfer can only be initiated by the creditor."
        );
        require(
            getDebt(from, to) >= _value,
            "The sender does not have such debt towards the receiver."
        );
        _reduceDebt(from, to, _value);

        _mediatedTransferReceiverPays(_value, _maxFee, _path, _extraData);
    }

    // Applies the onboarding rules before setting a trustline
    function _setTrustline(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen
    ) internal override {
        _applyOnboardingRules(_creditor, _debtor);
        super._setTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen
        );
    }

    function uniqueIdentifier(address _a, address _b)
        internal
        pure
        override(CurrencyNetworkBasicV2, DebtTracking)
        returns (bytes32)
    {
        return CurrencyNetworkBasicV2.uniqueIdentifier(_a, _b);
    }
}

// SPDX-License-Identifier: MIT
