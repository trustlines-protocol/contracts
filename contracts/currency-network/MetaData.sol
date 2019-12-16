pragma solidity ^0.5.8;


contract MetaData {

    string public name;
    string public symbol;
    uint8 public decimals;

    /**
     * @notice Initialize the meta data of the currency network
     * @param _name The name of the currency
     * @param _symbol The symbol of the currency
     * @param _decimals Number of decimals of the currency
     *
     */
    function init(
        string memory _name,
        string memory _symbol,
        uint8 _decimals
    )
        internal
    {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
    }
}
