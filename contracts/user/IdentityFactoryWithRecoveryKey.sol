pragma solidity 0.4.11;
import "./RecoverableController.sol";


contract IdentityFactoryWithRecoveryKey {
    event IdentityCreated(
        address indexed userKey,
        address proxy,
        address controller,
        address indexed recoveryKey);

    mapping(address => address) public senderToProxy;
    mapping(address => address) public recoveryToProxy;

    //cost ~2.4M gas
    function CreateProxyWithControllerAndRecoveryKey(address _adminKey, address _userKey, address _recoveryKey, uint _longTimeLock, uint _shortTimeLock, bytes32 _publicKeyUser) {
        Proxy proxy = new Proxy(_adminKey);
        RecoverableController controller = new RecoverableController(proxy, _userKey, _longTimeLock, _shortTimeLock, _publicKeyUser);
        proxy.transfer(controller);
        controller.changeRecoveryFromRecovery(_recoveryKey);

        IdentityCreated(_userKey, proxy, controller, _recoveryKey);
        senderToProxy[msg.sender] = proxy;
        recoveryToProxy[_recoveryKey] = proxy;
    }
}