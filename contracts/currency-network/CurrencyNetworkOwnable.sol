pragma solidity ^0.5.8;

import "./CurrencyNetwork.sol";
import "./CurrencyNetworkBasic.sol";


contract CurrencyNetworkOwnable is CurrencyNetwork {

    address public owner;

    /**
     * @dev Throws if called by any account other than the owner.
     */
    modifier onlyOwner() {
        require(owner == msg.sender, "Caller is not the owner");
        _;
    }

    function removeOwner() external onlyOwner {
        owner = address(0);
    }

    function setDebt(address debtor, address creditor, int value) external onlyOwner {
        _addToDebt(debtor, creditor, value);
    }

    /**
     * @notice Initialize the currency Network
     * @param _name The name of the currency
     * @param _symbol The symbol of the currency
     * @param _decimals Number of decimals of the currency
     * @param _capacityImbalanceFeeDivisor Divisor of the imbalance fee. The fee is 1 / _capacityImbalanceFeeDivisor
     * @param _defaultInterestRate The default interests for every trustlines in 0.01% per year
     * @param _customInterests Flag to allow or disallow trustlines to have custom interests
     * @param _preventMediatorInterests Flag to allow or disallow transactions resulting in loss of interests for
     *         intermediaries, unless the transaction exclusively reduces balances
     * @param _expirationTime Time after which the currency network is frozen and cannot be used anymore. Setting
     *         this value to zero disables freezing.
     */
    function init(
        string memory _name,
        string memory _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests,
        uint _expirationTime,
        address[] memory authorizedAddresses
    )
        public
    {
        owner = msg.sender;
        // super.init(_name, _symbol, _decimals);
        CurrencyNetworkBasic.init(_name, _symbol, _decimals, _capacityImbalanceFeeDivisor, _defaultInterestRate, _customInterests, _preventMediatorInterests, _expirationTime, authorizedAddresses);
    }
}
