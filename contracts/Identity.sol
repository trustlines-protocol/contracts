pragma solidity ^0.4.25;

import "./lib/ECDSA.sol";


contract Identity {

    address private owner;
    bool private initialised;

    constructor() public {
        // don't do anything here to allow usage of proxy contracts.
    }

    function init(address _owner) public {
        require(! initialised, "The contract has already been initialised.");
        owner = _owner;
        initialised = true;
    }

    function executeDelegatedTransaction(bytes _data, bytes _signature) public returns (bool _success) {
        require(isSignatureFromOwner(_data, _signature), "The provided data was signed by the owner of the identity.");
        _success = true;
    }

    function isSignatureFromOwner(bytes _data, bytes _signature) internal view returns (bool) {
        bytes32 hash = keccak256(_data);
        address signer = ECDSA.recover(hash, _signature);
        return owner == signer;
    }
}
