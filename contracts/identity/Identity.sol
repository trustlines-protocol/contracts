pragma solidity ^0.5.8;

import "../lib/ECDSA.sol";
import "../currency-network/DebtTracking.sol";
import "./ProxyStorage.sol";


contract Identity is ProxyStorage {

    uint constant public version  = 1;

    address public owner;
    uint public chainId;
    bool public initialised;

    mapping(bytes32 => bool) private hashUsed;
    uint public lastNonce = 0;
    // Divides the gas price value to allow for finer range of fee price
    uint constant public gasPriceDivisor = 1000000;

    event TransactionExecution(bytes32 hash, bool status);
    event FeePayment(uint value, address indexed recipient, address indexed currencyNetwork);
    event ContractDeployment(address deployed);

    constructor() public {
        // solium-disable-previous-line no-empty-blocks
        // don't do anything here to allow usage of proxy contracts.
    }

    // This contract can receive ether
    function () external payable {}

    function init(address _owner, uint _chainId) public {
        require(! initialised, "The contract has already been initialised.");
        owner = _owner;
        chainId = _chainId;
        initialised = true;
    }

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
    )
        public
    {
        bytes32 hash = transactionHash(
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
        require(validateSignature(hash, signature), "The transaction signature is not valid");

        if (nonce == 0) {
            hashUsed[hash] = true; // To prevent replaying this meta transaction
        } else {
            lastNonce++;
        }

        uint startGas = gasleft();
        require(startGas >= gasLimit, "Not enough gas left for operation");
        if (gasLimit == 0) {
            // Unlimited gas
            gasLimit = uint(-1);
        }

        bool status = applyOperation(to, value, data, operationType, gasLimit);

        uint256 gasSpent = startGas - gasleft();
        require(gasSpent <= gasLimit, "Gas limit too low");

        if ((gasPrice > 0 || baseFee > 0) && status != false) {
            uint256 fees = baseFee + gasSpent * gasPrice / gasPriceDivisor;
            require(fees >= baseFee, "Fees addition overflow");
            DebtTracking debtContract = DebtTracking(currencyNetworkOfFees);
            if (feeRecipient == address(0)) {
                feeRecipient = msg.sender;
            }
            debtContract.increaseDebt(feeRecipient, fees);
            emit FeePayment(fees, msg.sender, currencyNetworkOfFees);
        }

        emit TransactionExecution(hash, status);
    }

    function validateNonce(uint nonce, bytes32 hash) public view returns (bool) {
        if (nonce == 0) {
            return !hashUsed[hash];
        } else {
            return lastNonce + 1 == nonce;
        }

    }

    function validateTimeLimit(uint timeLimit) public view returns (bool) {
        if (timeLimit == 0) {
            return true;
        } else {
            return timeLimit >= now;
        }
    }

    function validateSignature(bytes32 hash, bytes memory _signature) public view returns (bool) {
        address signer = ECDSA.recover(hash, _signature);
        return owner == signer;
    }

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
    )
    public
    view
    returns (bytes32)
    {
        bytes32 hash = keccak256(
            abi.encodePacked(
                abi.encodePacked(
                    byte(0x19),
                    byte(0),
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
        uint gasLimit
    )
    internal
    returns (bool status)
    {
        if (operationType == 0) {
            // regular call
            (status, ) = to.call.value(value).gas(gasLimit)(data); // solium-disable-line
        } else if (operationType == 1) {
            // delegate call
            require(value == 0, "Cannot transfer value with DELEGATECALL");
            (status, ) = to.delegatecall.gas(gasLimit)(data);
        } else if (operationType == 2) {
            // regular create
            address deployed;
            //TODO how to limit gas here?
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
            //TODO how to limit gas here?
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
