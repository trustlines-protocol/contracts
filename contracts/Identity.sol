pragma solidity ^0.4.25;

import "./lib/ECDSA.sol";


contract Identity {

    address private owner;
    bool private initialised;

    mapping(bytes32 => bool) private hashUsed;

    event TransactionExecution(bytes32 hash, bool status);

    constructor() public {
        // don't do anything here to allow usage of proxy contracts.
    }

    // This contract can receive ether
    function () public payable {}

    function init(address _owner) public {
        require(! initialised, "The contract has already been initialised.");
        owner = _owner;
        initialised = true;
    }

    function executeTransaction(
        address from,
        address to,
        uint256 value,
        bytes data,
        uint256 nonce,
        bytes extraHash,
        bytes signature
    )
        public returns (bool _success)
    {

        require(from == address(this), "The transaction is not meant for this identity contract");

        bytes32 hash = transactionHash(
            from,
            to,
            value,
            data,
            nonce,
            extraHash
        );

        require(isSignatureValid(hash, signature), "The transaction signature is not valid");
        require(!hashUsed[hash], "This transaction was already executed");

        hashUsed[hash] = true; // To prevent replaying this meta transaction

        bool status = to.call.value(value)(data); // solium-disable-line security/no-call-value

        emit TransactionExecution(hash, status);

        _success = true;
    }

    function transactionHash(
        address from,
        address to,
        uint256 value,
        bytes data,
        uint256 nonce,
        bytes extraHash
    )
        internal
        pure
        returns (bytes32)
    {
        bytes32 dataHash = keccak256(data);

        bytes32 hash = keccak256(abi.encodePacked(
            byte(0x19),
            byte(0),
            from,
            to,
            value,
            dataHash,
            nonce,
            extraHash
        ));

        return hash;
    }

    function isSignatureValid(bytes32 _dataHash, bytes _signature) internal view returns (bool) {
        address signer = ECDSA.recover(_dataHash, _signature);
        return owner == signer;
    }
}
