pragma solidity ^0.4.0;

import "./Proxy.sol";

contract RecoverableController {

    uint    public version;
    Proxy   public proxy;
    address public userKey;
    address public proposedUserKey;
    uint    public proposedUserKeyPendingUntil;
    address public recoveryKey;
    address public proposedRecoveryKey;
    uint    public proposedRecoveryKeyPendingUntil;
    address public proposedController;
    uint    public proposedControllerPendingUntil;
    uint    public shortTimeLock;// use 900 for 15 minutes
    uint    public longTimeLock; // use 259200 for 3 days

    event RecoveryEvent(string action, address initiatedBy);

    modifier onlyUserKey() {if (msg.sender == userKey) _;}
    modifier onlyRecoveryKey() {if (msg.sender == recoveryKey) _;}

    function RecoverableController(address proxyAddress, address _userKey, uint _longTimeLock, uint _shortTimeLock) {
        version = 1;
        proxy = Proxy(proxyAddress);
        userKey = _userKey;
        shortTimeLock = _shortTimeLock;
        longTimeLock = _longTimeLock;
        recoveryKey = msg.sender;
    }

    // external trustlines functions

    function updateCreditline(address _debtor, uint32 _value) external {
        proxy.updateCreditline(_debtor, _value);
    }

    function acceptCreditline(address _debtor, uint32 _value) external returns (bool) {
        return proxy.acceptCreditline(_debtor, _value);
    }

    // public controller functions

    //pass 0x0 to cancel
    function signRecoveryChange(address _proposedRecoveryKey) public onlyUserKey {
        proposedRecoveryKeyPendingUntil = now + longTimeLock;
        proposedRecoveryKey = _proposedRecoveryKey;
        RecoveryEvent("signRecoveryChange", msg.sender);
    }

    function changeRecovery() public {
        if (proposedRecoveryKeyPendingUntil < now && proposedRecoveryKey != 0x0) {
            recoveryKey = proposedRecoveryKey;
            delete proposedRecoveryKey;
        }
    }

    //pass 0x0 to cancel
    function signControllerChange(address _proposedController) public onlyUserKey {
        proposedControllerPendingUntil = now + longTimeLock;
        proposedController = _proposedController;
        RecoveryEvent("signControllerChange", msg.sender);
    }

    function changeController() public {
        if (proposedControllerPendingUntil < now && proposedController != 0x0) {
            proxy.transfer(proposedController);
            suicide(proposedController);
        }
    }

    //pass 0x0 to cancel
    function signUserKeyChange(address _proposedUserKey) public onlyUserKey {
        proposedUserKeyPendingUntil = now + shortTimeLock;
        proposedUserKey = _proposedUserKey;
        RecoveryEvent("signUserKeyChange", msg.sender);
    }

    function changeUserKey() public {
        if (proposedUserKeyPendingUntil < now && proposedUserKey != 0x0) {
            userKey = proposedUserKey;
            delete proposedUserKey;
            RecoveryEvent("changeUserKey", msg.sender);
        }
    }

    function changeRecoveryFromRecovery(address _recoveryKey) public onlyRecoveryKey {
        recoveryKey = _recoveryKey;
    }

    function changeUserKeyFromRecovery(address _userKey) public onlyRecoveryKey {
        delete proposedUserKey;
        userKey = _userKey;
    }

    // public ERC20 functions

    function transfer(address to, uint value) public onlyUserKey {
        proxy.transfer(to, value);
    }

    function transferFrom(address from, address to, uint value) public {
        proxy.transferFrom(from, to, value);
    }

    function approve(address spender, uint value) public {
        proxy.approve(spender, value);
    }

    function balanceOf(address who) public constant returns (uint) {
        return proxy.balanceOf(who);
    }

    function allowance(address owner, address spender) public constant returns (uint) {
        return proxy.allowance(owner, spender);
    }

}

