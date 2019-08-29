pragma solidity ^0.5.8;

import "./CurrencyNetworkInterface.sol";

contract CurrencyNetworkRegistry {

    struct CurrencyNetworkMetadata {
        address author;
        string name;
        string symbol;
        uint8 decimals;
    }

    mapping (address => CurrencyNetworkMetadata) public networks;
    address[] public registeredNetworks;

    event NetworkAdded(address indexed _address, address _author, string _name, string _symbol, uint8 _decimals);

    function addNetwork(address _address) external {
        CurrencyNetworkInterface network;

        require(
            networks[_address].author == address(0) &&
            bytes(networks[_address].name).length == 0 &&
            bytes(networks[_address].symbol).length == 0
            , "CurrencyNetworks can only be registered once."
        );

        network = CurrencyNetworkInterface(_address);

        networks[_address] = CurrencyNetworkMetadata({
            author: msg.sender,
            name: network.name(),
            symbol: network.symbol(),
            decimals: network.decimals()
        });

        registeredNetworks.push(_address);

        emit NetworkAdded(
            _address,
            networks[_address].author,
            networks[_address].name,
            networks[_address].symbol,
            networks[_address].decimals
        );
    }

    function getNetworkCount() external view returns (uint256 _count) {
        return registeredNetworks.length;
    }

    function getNetworkAddress(uint256 _index) external view returns (address _network) {
        return registeredNetworks[_index];
    }

    function getNetworkMetadata(address _address) external view returns (address _author, string memory _name, string memory _symbol, uint8 _decimals) {
        return (
            networks[_address].author,
            networks[_address].name,
            networks[_address].symbol,
            networks[_address].decimals
        );
    }
}
