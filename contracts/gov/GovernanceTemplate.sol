pragma solidity ^0.4.11;


contract GovernanceTemplate {

    uint16 maxInterest;

    function GovernanceTemplate(uint16 _maxInterest) {}

    function validateTransfer(address _sender, address _receiver, uint16 _value) {
        assert(_value <= maxInterest);
    }

}
