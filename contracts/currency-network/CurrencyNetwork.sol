pragma solidity ^0.5.8;


import "../lib/it_set_lib.sol";
import "../tokens/Receiver_Interface.sol";
import "../lib/Ownable.sol";
import "../lib/Destructable.sol";
import "./CurrencyNetworkInterface.sol";
import "./DebtTracking.sol";
import "./Onboarding.sol";
import "../lib/ERC165.sol";
import "../lib/Authorizable.sol";
import "./MetaData.sol";
import "./CurrencyNetworkBasic.sol";


/**
 * CurrencyNetwork
 *
 * Main contract of Trustlines, encapsulates all trustlines of one currency network.
 * Implements functions to ripple payments in a currency network.
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

    // This function is rewritten from CurrencyNetworkBasic since it needs to apply onboarding rules
    // in this function, it is assumed _creditor is the initator of the trustline update (see _requestTrustlineUpdate())
    function _updateTrustline(
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
        require(! isNetworkFrozen, "The network is frozen and trustlines cannot be updated.");
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
        if (_isTrustlineFrozen(trustlineAgreement)) {
            require(! _isFrozen, "Trustline is frozen, it cannot be updated unless unfrozen.");
        }
        require(
            customInterests ||
            (_interestRateGiven == defaultInterestRate && _interestRateReceived == defaultInterestRate),
            "Interest rates given and received must be equal to default interest rates."
        );
        if (customInterests) {
            require(
                _interestRateGiven >= 0 && _interestRateReceived >= 0,
                "Only positive interest rates are supported."
            );
        }

        // reduction of creditlines and interests given is always possible if trustline is not frozen
        if (_creditlineGiven <= trustlineAgreement.creditlineGiven &&
            _creditlineReceived <= trustlineAgreement.creditlineReceived &&
            _interestRateGiven <= trustlineAgreement.interestRateGiven &&
            _interestRateReceived == trustlineAgreement.interestRateReceived &&
            _isFrozen == trustlineAgreement.isFrozen &&
            ! trustlineAgreement.isFrozen
        ) {
            _deleteTrustlineRequest(_creditor, _debtor);
            _setTrustline(
                _creditor,
                _debtor,
                _creditlineGiven,
                _creditlineReceived,
                _interestRateGiven,
                _interestRateReceived,
                _isFrozen
            );
            return;
        }

        TrustlineRequest memory trustlineRequest = _loadTrustlineRequest(_creditor, _debtor);

        // if original initiator is debtor, try to accept request
        if (trustlineRequest.initiator == _debtor) {
            if (_creditlineReceived <= trustlineRequest.creditlineGiven && _creditlineGiven <= trustlineRequest.creditlineReceived && _interestRateGiven <= trustlineRequest.interestRateReceived && _interestRateReceived == trustlineRequest.interestRateGiven && _isFrozen == trustlineRequest.isFrozen) {
                _deleteTrustlineRequest(_creditor, _debtor);
                // _debtor and _creditor is switched because we want the initiator of the trustline to be _debtor.
                // So every Given / Received has to be switched.
                _setTrustline(
                    _debtor,
                    _creditor,
                    _creditlineReceived,
                    _creditlineGiven,
                    _interestRateReceived,
                    _interestRateGiven,
                    _isFrozen
                );
                _applyOnboardingRules(_creditor, _debtor);
            } else {
                _requestTrustlineUpdate(
                    _creditor,
                    _debtor,
                    _creditlineGiven,
                    _creditlineReceived,
                    _interestRateGiven,
                    _interestRateReceived,
                    _isFrozen
                );
            }
        // update the trustline request
        } else {
            _requestTrustlineUpdate(
                _creditor,
                _debtor,
                _creditlineGiven,
                _creditlineReceived,
                _interestRateGiven,
                _interestRateReceived,
                _isFrozen
            );
        }
    }

}
