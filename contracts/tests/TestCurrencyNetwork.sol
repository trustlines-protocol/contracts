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
        string calldata _name,
        string calldata _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests) external
    {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
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

    /**
    * Set the trustline account between two users.
    * Can be removed once structs are supported in the ABI
    */
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
        require(
            customInterests ||
            (_interestRateGiven == defaultInterestRate && _interestRateReceived == defaultInterestRate),
            "Interest rates given and received must be equal to default interest rates."
        );
        if (customInterests) {
            require(
                _interestRateGiven >= 0 &&
                _interestRateReceived >= 0,
                "Only positive interest rates are supported."
            );
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

    /**
    * Set the trustline account between two users with default interests.
    * Can be removed once structs are supported in the ABI
    */
    function setAccountDefaultInterests(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int72 _balance
    )
        external
    {
        _setAccount(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            defaultInterestRate,
            defaultInterestRate,
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
