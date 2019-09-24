pragma solidity ^0.5.8;


contract IdentityFactory {

    event DeployedProxy(address proxyAddress);

    // bytes public identityProxyInitcode;

    constructor() public {
        // solium-disable-previous-line no-empty-blocks
        // We could potentially make deployment cheaper by storing the bytecode on chain
        // and sending only the constructor args to be appended to bytecode to make initcode.
    }

    function deployProxy(bytes memory initcode) public {
        address proxyAddress;

        // solium-disable-next-line security/no-inline-assembly
        assembly {
          proxyAddress := create2(0, add(initcode, 0x20), mload(initcode), 0)
          if iszero(extcodesize(proxyAddress)) {
            revert(0, 0)
          }
        }
        emit DeployedProxy(proxyAddress);
    }
}
