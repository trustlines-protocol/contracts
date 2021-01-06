pragma solidity ^0.8.0;

/**
 * @title Currency Network Interface
 * @notice Interface that currency networks must respect to be registered in the registry
 * @dev ERC-165 Interface Id: 0x7ecdffaf
 **/
interface CurrencyNetworkInterface {
    function name() external view returns (string memory);

    function symbol() external view returns (string memory);

    function decimals() external view returns (uint8);

    /**
     * @notice send `_value` along `_path`
     * The fees will be payed by the sender, so `_value` is the amount received by receiver
     * @param _value The amount to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path of transfer starting with msg.sender and ending with receiver
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transfer(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    ) external;

    /**
     * @notice send `_value` along `_path`
     * msg.sender needs to be authorized to call this function
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path of transfer starting with sender and ending with receiver
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transferFrom(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    ) external;

    /**
     * @notice returns what _to owes to _from
     * @param _from First address that defines the trustline
     * @param _to second address that defines the trustline
     * @return the amount _to owes to _from on the trustline between _from and _to
     **/
    function balance(address _from, address _to) external view returns (int256);

    /**
     * @notice The creditline limit given by `_creditor` to `_debtor`
     * @param _creditor the creditor of the queried trustline
     * @param _debtor the debtor of the queried trustline
     * @return credit limit given by creditor to debtor
     */
    function creditline(address _creditor, address _debtor)
        external
        view
        returns (uint256);

    event Transfer(
        address indexed _from,
        address indexed _to,
        uint256 _value,
        bytes _extraData
    );
}

// SPDX-License-Identifier: MIT
