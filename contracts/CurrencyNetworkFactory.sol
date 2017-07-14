pragma solidity ^0.4.0;

import "./lib/registry.sol";
import "./gov/GovernanceTemplate.sol";
import "./user/Proxy.sol";
import "./user/IdentityFactoryWithRecoveryKey.sol";

contract CurrencyNetworkFactory {
    event CurrencyNetworkCreated();

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
        uint16 _network_fee_divisor,
        uint16 _capacity_fee_divisor,
        uint16 _imbalance_fee_divisor,
        uint16 _maxInterestRate
    ) {
        GovernanceTemplate governance = new GovernanceTemplate(_maxInterestRate);
        address tokenAddr = 0x0;//CurrencyNetwork(_tokenName, _tokenSymbol, _network_fee_divisor, _capacity_fee_divisor, _imbalance_fee_divisor);
        registry.register(_tokenName, tokenAddr);
        Proxy proxy = new Proxy(tokenAddr);
        new IdentityFactoryWithRecoveryKey().CreateProxyWithControllerAndRecoveryKey(proxy, msg.sender, _delegates, 1000, 100);
    }
}
