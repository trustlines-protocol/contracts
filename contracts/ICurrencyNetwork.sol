pragma solidity ^0.4.0;

contract ICurrencyNetwork {

    function updateCreditline(address _debtor, uint32 _value) public;
    function acceptCreditline(address _creditor, uint32 _value) public returns (bool success);

}