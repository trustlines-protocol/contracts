pragma solidity ^0.5.8;

import "./ProxyStorage.sol";


contract IdentityProxy is ProxyStorage {

    constructor(address _identityImplementation) public {
        identityImplementation = _identityImplementation;
        // bytes4 initSignature = bytes4(keccak256("init(address)"));
        // (bool status, bytes memory returnedData) = identityImplementation.delegatecall(abi.encodePacked(initSignature, owner));
        // require(status, "Deployment failed.");
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
}
