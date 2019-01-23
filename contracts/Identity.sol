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

    function executeDelegatedTransaction(
        address from,
        address to,
        uint256 value,
        bytes data,
        uint nonce,
        bytes extraHash,
        bytes signature)
            public returns (bool _success) {

        bytes32 dataHash = keccak256(data);

        bytes32 data_to_sign = keccak256(
            byte(0x19),
            byte(0),
            from,
            to,
            value,
            dataHash,
            nonce,
            extraHash);

        require(isSignatureFromOwner(data_to_sign, signature), "The provided data was signed by the owner of the identity.");

        to.call.value(value)(data);
        _success = true;
    }

    function isSignatureFromOwner(bytes32 _dataHash, bytes _signature) internal view returns (bool) {
        address signer = ECDSA.recover(_dataHash, _signature);
        return owner == signer;
    }
}
