pragma solidity ^0.5.8;


import "./DebtTracking.sol";
import "./Onboarding.sol";
import "./CurrencyNetworkBasic.sol";


/**
 * CurrencyNetwork
 *
 * Extends basic currency networks to add debt tracking, debit transfer, and onboarding.
 *
 **/
contract CurrencyNetwork is CurrencyNetworkBasic, DebtTracking, Onboarding {

    /**
     * @notice send `_value` token to `_to` from `_from`
     * `_from` needs to have a debt towards `_to` of at least `_value`
     * `_to` needs to be msg.sender
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the receiver wants to pay
     * @param _path Path between _from and _to
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function debitTransfer(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    )
        external
        {
        require(_to == msg.sender, "The transfer can only be initiated by the creditor (_to).");
        require(getDebt(_from, _to) >= _value, "The sender does not have such debt towards the receiver.");
        _reduceDebt(_from, _to, _value);

        _mediatedTransferReceiverPays(
            _from,
            _to,
            _value,
            _maxFee,
            _path,
            _extraData
        );
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
    )
        internal
    {
        _applyOnboardingRules(_creditor, _debtor);
        super._setTrustline(_creditor, _debtor, _creditlineGiven, _creditlineReceived, _interestRateGiven, _interestRateReceived, _isFrozen);
    }
}
