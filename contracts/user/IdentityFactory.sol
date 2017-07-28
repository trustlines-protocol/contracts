pragma solidity 0.4.11;

import "./RecoveryQuorum.sol";

contract IdentityFactory {
    event IdentityCreated(
        address indexed userKey,
        address proxy,
        address controller,
        address recoveryQuorum);

    mapping(address => address) public senderToProxy;

    //cost ~2.4M gas
    function CreateProxyWithControllerAndRecovery(address _userKey, address[] _delegates, uint _longTimeLock, uint _shortTimeLock, bytes32 _publicKeyUser) {
        Proxy proxy = new Proxy();
        RecoverableController controller = new RecoverableController(proxy, _userKey, _longTimeLock, _shortTimeLock, _publicKeyUser);
        proxy.transfer(controller);
        RecoveryQuorum recoveryQuorum = new RecoveryQuorum(controller, _delegates);
        controller.changeRecoveryFromRecovery(recoveryQuorum);

        IdentityCreated(_userKey, proxy, controller, recoveryQuorum);
        senderToProxy[msg.sender] = proxy;
    }
}