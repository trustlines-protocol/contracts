pragma solidity ^0.8.0;

import "../lib/ECDSA.sol";
import "../currency-network/DebtTracking.sol";
import "./ProxyStorage.sol";

/**
 * @title On-chain identity and meta-transaction executing contract
 * @dev Represents a users on-chain identity and allows to execute meta-transactions where the gas of the ethereum transaction
        is not payed by the owner of the identity, but a delegate. The delegate can be payed in form of a debt
        within a Trustlines Currency Network.
 **/
contract Identity is ProxyStorage {
    /// Supported version of the meta transaction protocol
    uint256 public constant version = 1;

    /// Owner of the contract who controls what can be done with it
    address public owner;
    /// ChainId where this contract is deployed for replay protection
    uint256 public chainId;
    bool public initialised;

    mapping(bytes32 => bool) private hashUsed;
    uint256 public constant maxNonce = 2**255;
    uint256 public lastNonce = 0;
    /// Divides the gas price value to allow for finer range of fee price
    uint256 public constant gasPriceDivisor = 1000000;

    event TransactionExecution(bytes32 indexed hash, bool status);
    event TransactionCancellation(bytes32 indexed hash);
    event FeePayment(
        uint256 value,
        address indexed recipient,
        address indexed currencyNetwork
    );
    event ContractDeployment(address deployed);

    constructor() {
        // solium-disable-previous-line no-empty-blocks
        // don't do anything here to allow usage of proxy contracts.
    }

    // This contract can receive ether
    receive() external payable {}

    function init(address _owner, uint256 _chainId) public {
        require(!initialised, "The contract has already been initialised.");
        initialised = true;

        owner = _owner;
        chainId = _chainId;
    }

    /**
     * @notice Changes the implementation contract address to `_implementation`
     * @dev Changes the implementation contract if this identity uses a proxy. This allows to upgrade the
            functionality of a proxied identity contract to a newer protocol.
     *      Only works, if called via a proxy contract.
     * @param _implementation Address of the new identity implementation contract.
     **/
    function changeImplementation(address _implementation) public {
        require(
            msg.sender == address(this),
            "The implementation can only be changed by the contract itself"
        );
        implementation = _implementation;
        emit ImplementationChange(_implementation);
    }

    /**
     * @notice Executes the given meta-transaction
     * @param to Address where data should be executed and that will receive `value` coins
     * @param value Amount of coins to be sent to `to`
     * @param data Encoded function call to be executed at `to`
     * @param baseFee Fixed base fee in the selected currency network to be payed by this identity to
              `feeRecipient` if set, or `msg.sender`. Only has to be payed, if the meta-transaction succeeds.
     * @param gasPrice Price per 1M gas in the selected currency network to be payed by this contract to
              `feeRecipient` if set, or `msg.sender`. Only has to be payed, if the meta-transaction succeeds.
     * @param gasLimit Maximum amount of gas the meta-transaction can consume and the sender is willing to pay.
     * @param feeRecipient Recipient of the meta-transaction fee, or the zero address. If set to the zero address
              the fee goes to msg.sender.
     * @param currencyNetworkOfFees CurrencyNetwork in which to pay the fees.
     * @param nonce Number used once for replay protection. Can either be an increasing number to enforce the order
              of meta-transactions, and then must be equal to lastNonce + 1,
              or can be a random number >= `maxNonce` or 0 if the order does not matter. In the second case the hash of
              the meta-transaction is used for replay protection and the nonce can be used to generate a unique hash.
     * @param timeLimit Timestamp until when the meta transaction can be executed.
     * @param operationType How to apply `data` to `to`. Valid operation types are CALL(0), DELEGATECALL(1),
              CREATE(2) and CREATE2(3)
     * @param signature Signature of the meta transaction.
     **/
    // solium-disable-next-line security/no-assign-params
    function executeTransaction(
        address payable to,
        uint256 value,
        bytes memory data,
        uint256 baseFee,
        uint256 gasPrice,
        uint256 gasLimit,
        address feeRecipient,
        address currencyNetworkOfFees,
        uint256 nonce,
        uint256 timeLimit,
        uint8 operationType,
        bytes memory signature
    ) public {
        bytes32 hash =
            transactionHash(
                to,
                value,
                data,
                baseFee,
                gasPrice,
                gasLimit,
                feeRecipient,
                currencyNetworkOfFees,
                nonce,
                timeLimit,
                operationType
            );

        require(validateNonce(nonce, hash), "The transaction nonce is invalid");
        require(validateTimeLimit(timeLimit), "The transaction expired");
        require(
            validateSignature(hash, signature),
            "The transaction signature is not valid"
        );

        // We allow nonce >= maxNonce to be able to change the hash via changing the nonce
        // This allows for two meta-tx that would have the same hash otherwise
        if (nonce == 0 || nonce >= maxNonce) {
            hashUsed[hash] = true; // To prevent replaying this meta transaction
        } else {
            lastNonce++;
        }

        uint256 startGas = gasleft();
        require(startGas >= gasLimit, "Not enough gas left for operation");
        if (gasLimit == 0) {
            // Unlimited gas
            gasLimit = type(uint256).max;
        }

        bool status = applyOperation(to, value, data, operationType, gasLimit);

        uint256 gasSpent = startGas - gasleft();
        require(gasSpent <= gasLimit, "Gas limit too low");

        if ((gasPrice > 0 || baseFee > 0) && status != false) {
            uint256 fees = baseFee + (gasSpent * gasPrice) / gasPriceDivisor;
            require(fees >= baseFee, "Fees addition overflow");
            DebtTracking debtContract = DebtTracking(currencyNetworkOfFees);
            if (feeRecipient == address(0)) {
                feeRecipient = msg.sender;
            }
            debtContract.increaseDebt(feeRecipient, fees);
            emit FeePayment(fees, feeRecipient, currencyNetworkOfFees);
        }

        emit TransactionExecution(hash, status);
    }

    /**
     * @notice Cancels the meta-transaction with hash `txHash`
     * @dev Cancels a meta-transaction by invalidating the transaction hash
     * @param txHash hash of the meta-transaction to be cancelled
     **/
    function cancelTransaction(bytes32 txHash) public {
        require(
            msg.sender == owner || msg.sender == address(this),
            "Can only be called by owner or via meta-tx"
        );
        require(!hashUsed[txHash], "Transaction already executed or cancelled");
        hashUsed[txHash] = true;
        emit TransactionCancellation(txHash);
    }

    /**
     * Executes the given function call `data` at `to` and sends `value` coins
     * @dev Executes a function in the name of this identity. Reverts if the function call fails. Can only be called
               by the owner of this identity.
     * @param to The address where to execute the function and where to send `value` coins
     * @param value The amount of coins to send to `to`
     * @param data The encoded function call to be executed at `to`
     * @param timeLimit Timestamp until which this function call is allowed to be executed, afterwards it will revert
     * @param operationType How to apply `data` to `to`. Valid operation types are CALL(0), DELEGATECALL(1),
              CREATE(2) and CREATE2(3)
     **/
    function execute(
        address payable to,
        uint256 value,
        bytes memory data,
        uint256 timeLimit,
        uint8 operationType
    ) public {
        require(msg.sender == owner, "Only owner can call this");
        require(validateTimeLimit(timeLimit), "The transaction expired");

        bool status =
            applyOperation(to, value, data, operationType, type(uint256).max);

        require(status, "Transaction execution failed");
    }

    /**
     * @dev Validates the used nonce for replay protection and the transaction hash
     * @param nonce The nonce to be used
     * @param txHash The hash of the meta-transaction
     * @return True, if the nonce is correct and the txHash is unused, false otherwise
     **/
    function validateNonce(uint256 nonce, bytes32 txHash)
        public
        view
        returns (bool)
    {
        if (nonce == 0 || nonce >= maxNonce) {
            return !hashUsed[txHash];
        } else {
            return !hashUsed[txHash] && lastNonce + 1 == nonce;
        }
    }

    /**
     * @dev Validates if the timeLimit is still valid
     * @param timeLimit The timestamp to check. A zero timestamp will disable the timeLimit, and thus always succeed
     * @return True, if the timestamp is valid, false otherwise
     **/
    function validateTimeLimit(uint256 timeLimit) public view returns (bool) {
        if (timeLimit == 0) {
            return true;
        } else {
            return timeLimit >= block.timestamp;
        }
    }

    /**
     * @dev Validates the signature on a given hash
     **/
    function validateSignature(bytes32 hash, bytes memory _signature)
        public
        view
        returns (bool)
    {
        address signer = ECDSA.recover(hash, _signature);
        return owner == signer;
    }

    /**
     * @dev Calculates the meta-transaction hash from the meta-transaction fields and the identity fields
               For a description of the parameters, see executeTransaction
     * @return The transaction hash
     **/
    function transactionHash(
        address to,
        uint256 value,
        bytes memory data,
        uint256 baseFee,
        uint256 gasPrice,
        uint256 gasLimit,
        address feeRecipient,
        address currencyNetworkOfFees,
        uint256 nonce,
        uint256 timeLimit,
        uint8 operationType
    ) public view returns (bytes32) {
        bytes32 hash =
            keccak256(
                abi.encodePacked(
                    abi.encodePacked(
                        bytes1(0x19),
                        bytes1(0),
                        address(this),
                        chainId,
                        version
                    ),
                    abi.encodePacked(
                        to,
                        value,
                        keccak256(data),
                        baseFee,
                        gasPrice,
                        gasLimit,
                        feeRecipient,
                        currencyNetworkOfFees,
                        nonce,
                        timeLimit,
                        operationType
                    )
                )
            );

        return hash;
    }

    function applyOperation(
        address to,
        uint256 value,
        bytes memory data,
        uint8 operationType,
        uint256 gasLimit
    ) internal returns (bool status) {
        if (operationType == 0) {
            // regular call
            (status, ) = to.call{gas: gasLimit, value: value}(data); // solium-disable-line
        } else if (operationType == 1) {
            // delegate call
            require(value == 0, "Cannot transfer value with DELEGATECALL");
            (status, ) = to.delegatecall{gas: gasLimit}(data);
        } else if (operationType == 2) {
            // regular create
            address deployed;
            assembly {
                deployed := create(value, add(data, 0x20), mload(data))
            }
            status = (deployed != address(0));
            if (status) {
                emit ContractDeployment(deployed);
            }
        } else if (operationType == 3) {
            // create2
            address deployed;
            assembly {
                deployed := create2(value, add(data, 0x20), mload(data), 0)
            }
            status = (deployed != address(0));
            if (status) {
                emit ContractDeployment(deployed);
            }
        }
    }
}

// SPDX-License-Identifier: MIT
