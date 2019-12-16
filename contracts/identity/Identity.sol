pragma solidity ^0.5.8;

import "../lib/ECDSA.sol";
import "../DebtTracking.sol";
import "./ProxyStorage.sol";


contract Identity is ProxyStorage {

    address public owner;
    bool public initialised;

    mapping(bytes32 => bool) private hashUsed;
    uint public lastNonce = 0;

    event TransactionExecution(bytes32 hash, bool status);
    event FeesPaid(uint64 value, address currencyNetwork);

    constructor() public {
        // solium-disable-previous-line no-empty-blocks
        // don't do anything here to allow usage of proxy contracts.
    }

    // This contract can receive ether
    function () external payable {}

    function init(address _owner) public {
        require(! initialised, "The contract has already been initialised.");
        owner = _owner;
        initialised = true;
    }

    function executeTransaction(
        address from,
        address payable to,
        uint256 value,
        bytes memory data,
        uint64 fees,
        address currencyNetworkOfFees,
        uint256 nonce,
        bytes memory extraData,
        bytes memory signature
    )
        public returns (bool _success)
    {

        require(from == address(this), "The transaction is not meant for this identity contract");

        bytes32 hash = transactionHash(
            from,
            to,
            value,
            data,
            fees,
            currencyNetworkOfFees,
            nonce,
            extraData
        );

        require(validateSignature(hash, signature), "The transaction signature is not valid");
        require(validateNonce(nonce, hash), "The transaction nonce is invalid");

        if (nonce == 0) {
            hashUsed[hash] = true; // To prevent replaying this meta transaction
        } else {
            lastNonce++;
        }

        (bool status, ) = to.call.value(value)(data); // solium-disable-line
        emit TransactionExecution(hash, status);

        if (fees != 0 && status != false) {
            DebtTracking debtNetwork = DebtTracking(currencyNetworkOfFees);
            debtNetwork.increaseDebt(msg.sender, fees);
            emit FeesPaid(fees, currencyNetworkOfFees);
        }

        _success = true;
    }

    function validateNonce(uint nonce, bytes32 hash) public view returns (bool) {
        if (nonce == 0) {
            return !hashUsed[hash];
        } else {
            return lastNonce + 1 == nonce;
        }

    }

    function validateSignature(bytes32 hash, bytes memory _signature) public view returns (bool) {
        address signer = ECDSA.recover(hash, _signature);
        return owner == signer;
    }

    function transactionHash(
        address from,
        address to,
        uint256 value,
        bytes memory data,
        uint64 fees,
        address currencyNetworkOfFees,
        uint256 nonce,
        bytes memory extraData
    )
    internal
    pure
    returns (bytes32)
    {
        bytes32 dataHash = keccak256(data);

        bytes32 hash = keccak256(
            abi.encodePacked(
                byte(0x19),
                byte(0),
                from,
                to,
                value,
                dataHash,
                fees,
                currencyNetworkOfFees,
                nonce,
                extraData
            ));

        return hash;
    }
}
