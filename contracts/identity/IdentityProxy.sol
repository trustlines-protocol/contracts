pragma solidity ^0.5.8;

import "./ProxyStorage.sol";


contract IdentityProxy is ProxyStorage {

    constructor(address owner) public {
        // solium-disable-previous-line no-empty-blocks
        // we have the owner in the constructor so that it is part of the initcode
        // and the deployment address depends on the owner
    }

    function() external payable {
        address _identityImplementation = identityImplementation;

        // solium-disable-next-line security/no-inline-assembly
        assembly {
            // 0x40 contains the value for the next available free memory pointer.
            let ptr := mload(0x40)
            // Copy msg.data.
            calldatacopy(ptr, 0, calldatasize)
            // Call the implementation.
            // out and outsize are 0 because we don't know the size yet.
            let result := delegatecall(gas, _identityImplementation, ptr, calldatasize, 0, 0)
            // Copy the returned data.
            returndatacopy(ptr, 0, returndatasize)

            switch result
            // delegatecall returns 0 on error.
            case 0 { revert(ptr, returndatasize) }
            default { return(ptr, returndatasize) }
        }
    }

    function setImplementation(address _identityImplementation) public {
        if (identityImplementation == address(0)) {
            identityImplementation = _identityImplementation;
        } else {
            require(msg.sender == address(this), "The implementation can only be changed by the contract itself");
            identityImplementation = _identityImplementation;
        }
    }
}
