pragma solidity ^0.4.0;


contract CurrencyNetworkInterface {

    function balance(address _from, address _to) public constant returns (int);
    function creditline(address _creditor, address _debtor) public constant returns (int);
    //function transfer(address _to, uint _value, bytes data);  TODO decide how to implement
    event Transfer(address indexed _from, address indexed _to, uint _value, bytes _data);
    event CreditlineUpdate(address indexed _creditor, address indexed _debtor, uint32 _value);
}
