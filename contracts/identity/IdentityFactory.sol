pragma solidity ^0.5.8;

import "../lib/ECDSA.sol";


contract IdentityFactory {

    event DeployedProxy(address proxyAddress);

    // bytes public identityProxyInitcode;

    constructor() public {
        // solium-disable-previous-line no-empty-blocks
        // We could potentially make deployment cheaper by storing the bytecode on chain
        // and sending only the constructor args to be appended to bytecode to make initcode.
    }

    function deployProxy(bytes memory initcode, address implementationAddress, bytes memory signature) public {
        // we need to  check a signature there to make sure the owner authorized this implementationAddress
        address owner;
        assembly {
            // mload(initcode) is the size of initcode
            // initcode + mload(initcode) is the last word of initcode, so the owner
            owner := mload(add(initcode, mload(initcode)))
        }
        require(
            verifySignature(implementationAddress, owner, signature),
            "The given signature does not match the owner from the given initcode.");

        address proxyAddress;
        assembly {
          proxyAddress := create2(0, add(initcode, 0x20), mload(initcode), 0)
          if iszero(extcodesize(proxyAddress)) {
            revert(0, 0)
          }
        }

        // solium-disable-next-line security/no-low-level-calls
        (bool status,) = proxyAddress.call(abi.encodeWithSignature("setImplementation(address)", implementationAddress));
        require(status, "Could not set the implementation in the identity proxy.");

        // solium-disable-next-line security/no-low-level-calls
        (status,) = proxyAddress.call(abi.encodeWithSignature("init(address)", owner));
        require(status, "Could not set the owner in the identity proxy.");

        emit DeployedProxy(proxyAddress);
    }

    function verifySignature(address implementationAddress, address owner, bytes memory signature) internal returns (bool) {
        bytes32 hash = keccak256(
            abi.encodePacked(
                byte(0x19),
                byte(0),
                address(this),
                implementationAddress
            ));
        address signer = ECDSA.recover(hash, signature);
        return owner == signer;
    }
}
