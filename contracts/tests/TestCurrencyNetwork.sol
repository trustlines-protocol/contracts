pragma solidity ^0.5.8;

/*
  The sole purpose of this file is to be able to test the internal functions of
  the CurrencyNetwork or export test data to be used for testing the python
  implementation of these functions
*/


import "../CurrencyNetwork.sol";


contract TestCurrencyNetwork is CurrencyNetwork {

    function setCapacityImbalanceFeeDivisor(uint16 divisor)
        external
    {
        capacityImbalanceFeeDivisor = divisor;
    }

    function setNetworkSettings(
        string calldata _paramName,
        string calldata _paramSymbol,
        uint8 _paramDecimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests) external
    {
        _name = _paramName;
        _symbol = _paramSymbol;
        _decimals = _paramDecimals;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
        defaultInterestRate = _defaultInterestRate;
        customInterests = _customInterests;
        preventMediatorInterests = _preventMediatorInterests;
    }

    function testTransferSenderPays(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path)
        external
        returns (bool _success)
    {
        _success = _mediatedTransferSenderPays(
            _from,
            _to,
            _value,
            _maxFee,
            _path
        );
    }

    function testTransferReceiverPays(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path)
        external
        returns (bool _success)
    {
        _success = _mediatedTransferReceiverPays(
            _from,
            _to,
            _value,
            _maxFee,
            _path
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
