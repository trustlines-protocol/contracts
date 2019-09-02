pragma solidity ^0.5.8;

// ERC-165 Interface Id: 0x7ecdffaf
interface CurrencyNetworkInterface {

    function name() external view returns (string memory);
    function symbol() external view returns (string memory);
    function decimals() external view returns (uint8);

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

    function balance(address _from, address _to) external view returns (int);

    function creditline(address _creditor, address _debtor) external view returns (uint);

    event Transfer(address indexed _from, address indexed _to, uint _value, bytes _extraData);

}
