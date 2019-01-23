pragma solidity ^0.4.25;

/*
  The sole purpose of this file is to be able to test the internal functions of
  the CurrencyNetwork or export test data to be used for testing the python
  implementation of these functions
*/


import "../CurrencyNetwork.sol";


contract TestCurrencyNetwork is CurrencyNetwork {
    constructor() public {
        // don't do anything here due to upgradeability issues (no constructor-call on replacement).
    }

    function setCapacityImbalanceFeeDivisor(uint16 divisor)
        external
    {
        capacityImbalanceFeeDivisor = divisor;
    }

    function testTransferSenderPays(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] _path)
        external
        returns (bool _success)
    {
        _success = _mediatedTransferSenderPays(_from, _to, _value, _maxFee, _path);
    }

    function testTransferReceiverPays(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] _path)
        external
        returns (bool _success)
    {
        _success = _mediatedTransferReceiverPays(_from, _to, _value, _maxFee, _path);
    }

    // XXX we already have setAccount inm CurrencyNetwork, but I cannot call it.
    // onlyOwner won't let me. why??
    function setAccount(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int72 _balance
    )
        external
    {
        require(customInterests || (_interestRateGiven == defaultInterestRate && _interestRateReceived == defaultInterestRate));
        if (customInterests) {
            require(_interestRateGiven >= 0 && _interestRateReceived >= 0);
        }

        _setAccount(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _feesOutstandingA,
            _feesOutstandingB,
            _mtime,
            _balance
        );
    }

    function testCalculateFees(uint64 _imbalanceGenerated, uint16 _capacityImbalanceFeeDivisor)
        public pure
        returns (uint64)
    {
        return _calculateFees(_imbalanceGenerated, _capacityImbalanceFeeDivisor);
    }

    function testCalculateFeesReverse(uint64 _imbalanceGenerated, uint16 _capacityImbalanceFeeDivisor)
        public pure
        returns (uint64)
    {
        return _calculateFeesReverse(_imbalanceGenerated, _capacityImbalanceFeeDivisor);
    }

    function testImbalanceGenerated(
        uint64 _value,
        int72 _balance
    )
        public pure
        returns (uint64)
    {
        return _imbalanceGenerated(_value, _balance);
    }
}
