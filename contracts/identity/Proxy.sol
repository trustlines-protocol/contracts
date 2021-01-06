pragma solidity ^0.8.0;

import "./ProxyStorage.sol";

/**
 * @title Proxy contract that forwards all calls to the implementation contract via a DELEGATECALL
 **/
contract Proxy is ProxyStorage {
    constructor(address owner) {
        // solium-disable-previous-line no-empty-blocks
        // we have the owner in the constructor so that it is part of the initcode
        // and the deployment address depends on the owner
    }

    receive() external payable {
        address _implementation = implementation;

        // solium-disable-next-line security/no-inline-assembly
        assembly {
            // 0x40 contains the value for the next available free memory pointer.
            let ptr := mload(0x40)
            // Copy msg.data.
            calldatacopy(ptr, 0, calldatasize())
            // Call the implementation.
            // out and outsize are 0 because we don't know the size yet.
            let result := delegatecall(
                gas(),
                _implementation,
                ptr,
                calldatasize(),
                0,
                0
            )
            // Copy the returned data.
            returndatacopy(ptr, 0, returndatasize())

            switch result
                // delegatecall returns 0 on error.
                case 0 {
                    revert(ptr, returndatasize())
                }
                default {
                    return(ptr, returndatasize())
                }
        }
    }

    function setImplementation(address _implementation) public {
        require(implementation == address(0), "Implementation already set");
        implementation = _implementation;
        emit ImplementationChange(_implementation);
    }
}

// SPDX-License-Identifier: MIT
