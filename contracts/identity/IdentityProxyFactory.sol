pragma solidity ^0.5.8;

import "../lib/ECDSA.sol";
import "./Proxy.sol";
import "./Identity.sol";


contract IdentityProxyFactory {

    event ProxyDeployment(address owner, address proxyAddress, address implementationAddress);

    uint public chainId;

    constructor(uint _chainId) public {
        chainId = _chainId;
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

        address payable proxyAddress;
        assembly {
          proxyAddress := create2(0, add(initcode, 0x20), mload(initcode), 0)
          if iszero(extcodesize(proxyAddress)) {
            revert(0, 0)
          }
        }

        Proxy(proxyAddress).setImplementation(implementationAddress);
        Identity(proxyAddress).init(owner, chainId);

        emit ProxyDeployment(owner, proxyAddress, implementationAddress);
    }

    function verifySignature(address implementationAddress, address owner, bytes memory signature) internal view returns (bool) {
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
