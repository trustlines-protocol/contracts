pragma solidity ^0.8.0;

/*
  The sole purpose of this file is to be able to test the internal functions of
  the CurrencyNetwork or export test data to be used for testing the python
  implementation of these functions
*/

import "../currency-network/CurrencyNetworkOwnable.sol";

contract TestCurrencyNetwork is CurrencyNetworkOwnable {
    function setCapacityImbalanceFeeDivisor(uint16 divisor) external {
        capacityImbalanceFeeDivisor = divisor;
    }

    function setNetworkSettings(
        string calldata _name,
        string calldata _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests
    ) external {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
        defaultInterestRate = _defaultInterestRate;
        customInterests = _customInterests;
        preventMediatorInterests = _preventMediatorInterests;
    }

    function testTransferSenderPays(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path
    ) external {
        _mediatedTransferSenderPays(_value, _maxFee, _path, "");
    }

    function testTransferReceiverPays(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path
    ) external {
        _mediatedTransferReceiverPays(_value, _maxFee, _path, "");
    }

    function setAccount(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen,
        uint32 _mtime,
        int72 _balance
    ) external override {
        _setAccount(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen,
            _mtime,
            _balance
        );
    }

    function setAccountDefaultInterests(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        bool _isFrozen,
        uint32 _mtime,
        int72 _balance
    ) external {
        _setAccount(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            defaultInterestRate,
            defaultInterestRate,
            _isFrozen,
            _mtime,
            _balance
        );
    }

    function testAddToDebt(
        address debtor,
        address creditor,
        int256 value
    ) external {
        _addToDebt(debtor, creditor, value);
    }

    function testCalculateFees(
        uint64 _imbalanceGenerated,
        uint16 _capacityImbalanceFeeDivisor
    ) public pure returns (uint64) {
        return
            _calculateFees(_imbalanceGenerated, _capacityImbalanceFeeDivisor);
    }

    function testCalculateFeesReverse(
        uint64 _imbalanceGenerated,
        uint16 _capacityImbalanceFeeDivisor
    ) public pure returns (uint64) {
        return
            _calculateFeesReverse(
                _imbalanceGenerated,
                _capacityImbalanceFeeDivisor
            );
    }

    function testImbalanceGenerated(uint64 _value, int72 _balance)
        public
        pure
        returns (uint64)
    {
        return _calculateImbalanceGenerated(_value, _balance);
    }

    function testCalculateBalanceWithInterests(
        int72 _balance,
        uint256 _startTime,
        uint256 _endTime,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    ) public pure returns (int72) {
        return
            calculateBalanceWithInterests(
                _balance,
                _startTime,
                _endTime,
                _interestRateGiven,
                _interestRateReceived
            );
    }

    function testFreezeNetwork() public {
        isNetworkFrozen = true;
        emit NetworkFreeze();
    }

    function testUnfreezeNetwork() public {
        isNetworkFrozen = false;
        emit NetworkUnfreeze();
    }

    function init(
        string memory _name,
        string memory _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests,
        uint256 _expirationTime,
        address[] memory authorizedAddresses
    ) public override {
        CurrencyNetworkBasic.init(
            _name,
            _symbol,
            _decimals,
            _capacityImbalanceFeeDivisor,
            _defaultInterestRate,
            _customInterests,
            _preventMediatorInterests,
            _expirationTime,
            authorizedAddresses
        );
    }

    function _setAccount(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen,
        uint32 _mtime,
        int72 _balance
    ) internal {
        TrustlineAgreement memory trustlineAgreement;
        trustlineAgreement.creditlineGiven = _creditlineGiven;
        trustlineAgreement.creditlineReceived = _creditlineReceived;
        trustlineAgreement.interestRateGiven = _interestRateGiven;
        trustlineAgreement.interestRateReceived = _interestRateReceived;
        trustlineAgreement.isFrozen = _isFrozen;

        TrustlineBalances memory trustlineBalances;
        trustlineBalances.mtime = _mtime;
        trustlineBalances.balance = _balance;

        _storeTrustlineAgreement(_a, _b, trustlineAgreement);
        _storeTrustlineBalances(_a, _b, trustlineBalances);

        addToUsersAndFriends(_a, _b);
        _applyOnboardingRules(_a, NO_ONBOARDER);
        _applyOnboardingRules(_b, NO_ONBOARDER);

        emit TrustlineUpdate(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen
        );
        // Be aware that a BalanceUpdate event is missing, as it would not inform about the balance
        // at the correct `_mtime` since `_mtime` is not an argument of the event.
    }
}

// SPDX-License-Identifier: MIT
