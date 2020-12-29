pragma solidity ^0.8.0;

import "../lib/ECDSA.sol";
import "./Proxy.sol";
import "./Identity.sol";

/**
 * @title Factory to create proxy contracts
 **/

contract IdentityProxyFactory {
    event ProxyDeployment(
        address owner,
        address proxyAddress,
        address implementationAddress
    );

    uint256 public chainId;

    constructor(uint256 _chainId) {
        chainId = _chainId;
    }

    /**
     * @notice Deploys a proxy contract by executing `initcode` and set the implementation at `implementation`
     * @dev Deploys a proxy contract. Checks the given signature to make sure the right implementation address is set.
     * @param initcode The initcode to be executed for contract creation
     * @param implementation The address of the implementation to set
     * @param signature Signature of owner of the used implementation address
     **/
    function deployProxy(
        bytes memory initcode,
        address implementation,
        bytes memory signature
    ) public {
        // we need to  check a signature there to make sure the owner authorized this implementationAddress
        address owner;
        assembly {
            // mload(initcode) is the size of initcode
            // initcode + mload(initcode) is the last word of initcode, so the owner
            owner := mload(add(initcode, mload(initcode)))
        }
        require(
            verifySignature(implementation, owner, signature),
            "The given signature does not match the owner from the given initcode."
        );

        address payable proxyAddress;
        assembly {
            proxyAddress := create2(0, add(initcode, 0x20), mload(initcode), 0)
            if iszero(extcodesize(proxyAddress)) {
                revert(0, 0)
            }
        }

        Proxy(proxyAddress).setImplementation(implementation);
        Identity(proxyAddress).init(owner, chainId);

        emit ProxyDeployment(owner, proxyAddress, implementation);
    }

    function verifySignature(
        address implementationAddress,
        address owner,
        bytes memory signature
    ) internal view returns (bool) {
        bytes32 hash =
            keccak256(
                abi.encodePacked(
                    bytes1(0x19),
                    bytes1(0),
                    address(this),
                    implementationAddress
                )
            );
        address signer = ECDSA.recover(hash, signature);
        return owner == signer;
    }
}

// SPDX-License-Identifier: MIT
