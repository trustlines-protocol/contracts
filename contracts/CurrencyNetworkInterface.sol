pragma solidity ^0.5.8;


contract CurrencyNetworkInterface {

    function transfer(
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    )
        external
        returns (bool success);

    function transferFrom(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    )
        external
        returns (bool success);

    function balance(address _from, address _to) public view returns (int);

    function creditline(address _creditor, address _debtor) public view returns (uint);

    event Transfer(address indexed _from, address indexed _to, uint _value, bytes _extraData);

}
