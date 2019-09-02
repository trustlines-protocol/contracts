pragma solidity ^0.5.8;

import "./CurrencyNetworkInterface.sol";
import "./lib/ERC165Query.sol";


contract CurrencyNetworkRegistry is ERC165Query {

    struct CurrencyNetworkMetadata {
        address registeredBy;
        string name;
        string symbol;
        uint8 decimals;
    }

    mapping (address => CurrencyNetworkMetadata) internal currencyNetworks;
    address[] internal registeredCurrencyNetworks;

    event CurrencyNetworkAdded(
        address indexed _address,
        address indexed _registeredBy,
        string _name,
        string _symbol,
        uint8 _decimals
    );

    function addCurrencyNetwork(address _address) external {
        CurrencyNetworkInterface network;

        require(
            currencyNetworks[_address].registeredBy == address(0) &&
            bytes(currencyNetworks[_address].name).length == 0 &&
            bytes(currencyNetworks[_address].symbol).length == 0,
            "CurrencyNetworks can only be registered once."
        );

        network = CurrencyNetworkInterface(_address);

        require(
            this.doesContractImplementInterface(
                _address,
                network.transfer.selector ^
                network.transferFrom.selector ^
                network.balance.selector ^
                network.creditline.selector
            ),
            "CurrencyNetworks need to implement ERC165 and CurrencyNetworkInterface"
        );

        currencyNetworks[_address] = CurrencyNetworkMetadata({
            registeredBy: msg.sender,
            name: network.name(),
            symbol: network.symbol(),
            decimals: network.decimals()
        });

        registeredCurrencyNetworks.push(_address);

        emit CurrencyNetworkAdded(
            _address,
            currencyNetworks[_address].registeredBy,
            currencyNetworks[_address].name,
            currencyNetworks[_address].symbol,
            currencyNetworks[_address].decimals
        );
    }

    function getCurrencyNetworkCount() external view returns (uint256 _count) {
        return registeredCurrencyNetworks.length;
    }

    function getCurrencyNetworkAddress(uint256 _index) external view returns (address _network) {
        return registeredCurrencyNetworks[_index];
    }

    function getCurrencyNetworkMetadata(
        address _address
    )
        external
        view
        returns (
            address _registeredBy,
            string memory _name,
            string memory _symbol,
            uint8 _decimals
        )
    {
        return (
            currencyNetworks[_address].registeredBy,
            currencyNetworks[_address].name,
            currencyNetworks[_address].symbol,
            currencyNetworks[_address].decimals
        );
    }
}
