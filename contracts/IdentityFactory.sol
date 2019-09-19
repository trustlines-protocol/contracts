pragma solidity ^0.5.8;

import "./lib/ECDSA.sol";
import "./debtTrackingInterface.sol";


contract IdentityFactory {

    event DeployedIdentity(address identity, address owner);

    bytes public identityInitcode;

    constructor(bytes memory _identityInitcode) public {
        identityInitcode = _identityInitcode;
    }

    function deployIdentity(address owner) public {
        address identityAddress;
        bytes memory initcode = identityInitcode;
        assembly {
          identityAddress := create2(0, add(initcode, 0x20), mload(initcode), 0)
          if iszero(extcodesize(identityAddress)) {
            revert(0, 0)
          }
        }
        emit DeployedIdentity(identityAddress, owner);
    }

}
