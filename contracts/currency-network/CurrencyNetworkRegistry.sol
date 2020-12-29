pragma solidity ^0.8.0;

import "./CurrencyNetworkInterface.sol";
import "../lib/ERC165Query.sol";

/**
 * @title Currency Network Registry
 * @notice Used to keep an on-chain registry of currency networks
 * @dev Currency networks must implement the CurrencyNetworkInterface with ERC-165 interface id: 0x7ecdffaf
 **/
contract CurrencyNetworkRegistry is ERC165Query {
    struct CurrencyNetworkMetadata {
        address firstRegistrationBy;
        string name;
        string symbol;
        uint8 decimals;
    }

    mapping(address => CurrencyNetworkMetadata) internal currencyNetworks;
    address[] internal registeredCurrencyNetworks;
    mapping(address => address[]) internal currencyNetworksRegisteredBy;

    event CurrencyNetworkAdded(
        address indexed _address,
        address indexed _registeredBy,
        string _name,
        string _symbol,
        uint8 _decimals
    );

    function addCurrencyNetwork(address _address) external {
        CurrencyNetworkInterface network;

        network = CurrencyNetworkInterface(_address);

        require(
            // ERC-165 check is always done implicitly
            this.doesContractImplementInterface(
                _address,
                network.name.selector ^
                    network.symbol.selector ^
                    network.decimals.selector ^
                    network.transfer.selector ^
                    network.transferFrom.selector ^
                    network.balance.selector ^
                    network.creditline.selector
            ),
            "CurrencyNetworks need to implement ERC165 and CurrencyNetworkInterface"
        );

        if (
            currencyNetworks[_address].firstRegistrationBy == address(0) &&
            bytes(currencyNetworks[_address].name).length == 0 &&
            bytes(currencyNetworks[_address].symbol).length == 0
        ) {
            currencyNetworks[_address] = CurrencyNetworkMetadata({
                firstRegistrationBy: msg.sender,
                name: network.name(),
                symbol: network.symbol(),
                decimals: network.decimals()
            });

            registeredCurrencyNetworks.push(_address);
        }

        emit CurrencyNetworkAdded(
            _address,
            msg.sender,
            currencyNetworks[_address].name,
            currencyNetworks[_address].symbol,
            currencyNetworks[_address].decimals
        );

        currencyNetworksRegisteredBy[msg.sender].push(_address);
    }

    function getCurrencyNetworkCount() external view returns (uint256) {
        return registeredCurrencyNetworks.length;
    }

    function getCurrencyNetworkAddress(uint256 _index)
        external
        view
        returns (address)
    {
        return registeredCurrencyNetworks[_index];
    }

    function getCurrencyNetworkMetadata(address _address)
        external
        view
        returns (
            address _firstRegistrationBy,
            string memory _name,
            string memory _symbol,
            uint8 _decimals
        )
    {
        return (
            currencyNetworks[_address].firstRegistrationBy,
            currencyNetworks[_address].name,
            currencyNetworks[_address].symbol,
            currencyNetworks[_address].decimals
        );
    }

    function getCurrencyNetworksRegisteredBy(address _address)
        external
        view
        returns (address[] memory)
    {
        return currencyNetworksRegisteredBy[_address];
    }
}

// SPDX-License-Identifier: MIT
