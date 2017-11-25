pragma solidity ^0.4.11;


import "./lib/registry.sol";
import "./gov/GovernanceTemplate.sol";
import "./CurrencyNetwork.sol";


contract CurrencyNetworkFactory {

    event CurrencyNetworkCreated(address _currencyNetworkContract);

    Registry private registry;

    function CurrencyNetworkFactory(address _registry) public {
        registry = Registry(_registry);
    }

    //cost XXXXXXX gas
    function CreateCurrencyNetwork(
        string _tokenName,
        string _tokenSymbol,
        address _adminKey,
        uint16 _network_fee_divisor,
        uint16 _capacityImbalanceFeeDivisor,
        uint16 _maxInterestRate
    ) external
    {
        // GovernanceTemplate governance = new GovernanceTemplate(_maxInterestRate);
        address tokenAddr = new CurrencyNetwork();
        registry.register(_tokenName, tokenAddr);
        CurrencyNetworkCreated(tokenAddr);
    }
}
