pragma solidity ^0.4.11;

contract ICurrencyNetwork {

    function updateCreditline(address _debtor, uint32 _value) external;
    function acceptCreditline(address _creditor, uint32 _value) external returns (bool success);

}
