pragma solidity ^0.4.0;

import "./lib/registry.sol";
import "./gov/GovernanceTemplate.sol";
import "./user/Proxy.sol";
import "./user/IdentityFactoryWithRecoveryKey.sol";
import "./EternalStorage.sol";
import "./CurrencyNetwork.sol";

contract CurrencyNetworkFactory {

    event CurrencyNetworkCreated(address _currencyNetworkContract);

    Registry private registry;

    function CurrencyNetworkFactory(address _registry) {
        registry = Registry(registry);
    }

    //cost XXXXXXX gas
    function CreateCurrencyNetwork
    (
        bytes29 _tokenName,
        bytes3 _tokenSymbol,
        address _delegates,
        address _adminKey,
        uint16 _network_fee_divisor,
        uint16 _capacity_fee_divisor,
        uint16 _imbalance_fee_divisor,
        uint16 _maxInterestRate
    ) {
        GovernanceTemplate governance = new GovernanceTemplate(_maxInterestRate);
        EternalStorage es = new EternalStorage(_adminKey);
        address tokenAddr = new CurrencyNetwork(_tokenName, _tokenSymbol, address(es));
        registry.register(_tokenName, tokenAddr);
        CurrencyNetworkCreated(tokenAddr);
    }
}
