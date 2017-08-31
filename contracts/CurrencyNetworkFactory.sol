pragma solidity ^0.4.11;

import "./lib/registry.sol";
import "./gov/GovernanceTemplate.sol";
import "./user/Proxy.sol";
import "./user/IdentityFactoryWithRecoveryKey.sol";
import "./EternalStorage.sol";
import "./CurrencyNetwork.sol";

contract CurrencyNetworkFactory {

    event CurrencyNetworkCreated(address _currencyNetworkContract, address _eternalStorage);

    Registry private registry;

    function CurrencyNetworkFactory(address _registry) {
        registry = Registry(_registry);
    }

    //cost XXXXXXX gas
    function CreateCurrencyNetwork
    (
        string _tokenName,
        string _tokenSymbol,
        address _adminKey,
        uint16 _network_fee_divisor,
        uint16 _capacity_fee_divisor,
        uint16 _imbalance_fee_divisor,
        uint16 _maxInterestRate
    ) {
        GovernanceTemplate governance = new GovernanceTemplate(_maxInterestRate);
        EternalStorage es = new EternalStorage(_adminKey);
        address tokenAddr = new CurrencyNetwork(_tokenName, _tokenSymbol, address(es), _network_fee_divisor, _capacity_fee_divisor, _imbalance_fee_divisor, _maxInterestRate);
        es.transfer(tokenAddr);
        registry.register(_tokenName, tokenAddr);
        CurrencyNetworkCreated(tokenAddr, es);
    }
}
