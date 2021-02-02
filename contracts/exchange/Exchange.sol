/*

  Copyright 2017 ZeroEx Intl.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

*/

pragma solidity ^0.8.0;

import "../tokens/Token.sol";
import "../currency-network/CurrencyNetworkInterface.sol";

/// @title Exchange - Facilitates exchange of ERC20 tokens.
/// @author Amir Bandeali - <amir@0xProject.com>, Will Warren - <will@0xProject.com>
contract Exchange {
    // Error Codes
    enum Errors {
        ORDER_EXPIRED, // Order has already expired
        ORDER_FULLY_FILLED_OR_CANCELLED, // Order has already been fully filled or cancelled
        ROUNDING_ERROR_TOO_LARGE, // Rounding error too large
        INSUFFICIENT_BALANCE_OR_ALLOWANCE // Insufficient balance or allowance for token transfer
    }

    string public constant VERSION = "1.0.0";
    uint16 public constant EXTERNAL_QUERY_GAS_LIMIT = 4999; // Changes to state require at least 5000 gas

    // Trustlines variables
    uint32 public constant MAX_FEE = 100;

    // Mappings of orderHash => amounts of takerTokenAmount filled or cancelled.
    mapping(bytes32 => uint256) public filled;
    mapping(bytes32 => uint256) public cancelled;

    event LogFill(
        address indexed maker,
        address taker,
        address indexed feeRecipient,
        address makerToken,
        address takerToken,
        uint256 filledMakerTokenAmount,
        uint256 filledTakerTokenAmount,
        uint256 paidMakerFee,
        uint256 paidTakerFee,
        bytes32 indexed tokens, // keccak256(makerToken, takerToken), allows subscribing to a token pair
        bytes32 orderHash
    );

    event LogCancel(
        address indexed maker,
        address indexed feeRecipient,
        address makerToken,
        address takerToken,
        uint256 cancelledMakerTokenAmount,
        uint256 cancelledTakerTokenAmount,
        bytes32 indexed tokens,
        bytes32 orderHash
    );

    event LogError(uint8 indexed errorId, bytes32 indexed orderHash);

    struct Order {
        address maker;
        address taker;
        address makerToken;
        address takerToken;
        address feeRecipient;
        uint256 makerTokenAmount;
        uint256 takerTokenAmount;
        uint256 makerFee;
        uint256 takerFee;
        uint256 expirationTimestampInSec;
        bytes32 orderHash;
    }

    constructor() {
        // solium-disable-previous-line no-empty-blocks
    }

    /*
     * Core exchange functions
     */

    /// @dev Fills the input order.
    /// @param orderAddresses Array of order's maker, taker, makerToken, takerToken, and feeRecipient.
    /// @param orderValues Array of order's makerTokenAmount, takerTokenAmount, makerFee, takerFee, expirationTimestampInSec, and salt.
    /// @param fillTakerTokenAmount Desired amount of takerToken to fill.
    /// @param shouldThrowOnInsufficientBalanceOrAllowance Test if transfer will fail before attempting.
    /// @param v ECDSA signature parameter v.
    /// @param r ECDSA signature parameters r.
    /// @param s ECDSA signature parameters s.
    /// @return filledTakerTokenAmount Total amount of takerToken filled in trade.
    function fillOrder(
        address[5] memory orderAddresses,
        uint256[6] memory orderValues,
        uint256 fillTakerTokenAmount,
        bool shouldThrowOnInsufficientBalanceOrAllowance,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public returns (uint256 filledTakerTokenAmount) {
        shouldThrowOnInsufficientBalanceOrAllowance; // This line is just to disable solc warnings
        Order memory order =
            Order({
                maker: orderAddresses[0],
                taker: orderAddresses[1],
                makerToken: orderAddresses[2],
                takerToken: orderAddresses[3],
                feeRecipient: orderAddresses[4],
                makerTokenAmount: orderValues[0],
                takerTokenAmount: orderValues[1],
                makerFee: orderValues[2],
                takerFee: orderValues[3],
                expirationTimestampInSec: orderValues[4],
                orderHash: getOrderHash(orderAddresses, orderValues)
            });

        require(
            order.taker == address(0) || order.taker == msg.sender,
            "Taker of order must be message sender or zero address."
        );
        require(
            order.makerTokenAmount > 0 &&
                order.takerTokenAmount > 0 &&
                fillTakerTokenAmount > 0,
            "Token amount of order maker, order taker, and fill taker must be positive."
        );
        require(
            isValidSignature(order.maker, order.orderHash, v, r, s),
            "The signature of the order is incorrect."
        );

        if (block.timestamp >= order.expirationTimestampInSec) {
            emit LogError(uint8(Errors.ORDER_EXPIRED), order.orderHash);
            return 0;
        }

        uint256 remainingTakerTokenAmount =
            order.takerTokenAmount -
                getUnavailableTakerTokenAmount(order.orderHash);
        filledTakerTokenAmount = min256(
            fillTakerTokenAmount,
            remainingTakerTokenAmount
        );
        if (filledTakerTokenAmount == 0) {
            emit LogError(
                uint8(Errors.ORDER_FULLY_FILLED_OR_CANCELLED),
                order.orderHash
            );
            return 0;
        }

        if (
            isRoundingError(
                filledTakerTokenAmount,
                order.takerTokenAmount,
                order.makerTokenAmount
            )
        ) {
            emit LogError(
                uint8(Errors.ROUNDING_ERROR_TOO_LARGE),
                order.orderHash
            );
            return 0;
        }

        uint256 filledMakerTokenAmount =
            getPartialAmount(
                filledTakerTokenAmount,
                order.takerTokenAmount,
                order.makerTokenAmount
            );
        uint256 paidMakerFee;
        uint256 paidTakerFee;
        filled[order.orderHash] =
            filled[order.orderHash] +
            filledTakerTokenAmount;
        require(
            Token(order.makerToken).transferFrom(
                order.maker,
                msg.sender,
                filledMakerTokenAmount
            ),
            "The maker token cannot be transferred from the maker to the taker."
        );
        require(
            Token(order.takerToken).transferFrom(
                msg.sender,
                order.maker,
                filledTakerTokenAmount
            ),
            "The taker token cannot be transferred from the taker to the maker."
        );

        emit LogFill(
            order.maker,
            msg.sender,
            order.feeRecipient,
            order.makerToken,
            order.takerToken,
            filledMakerTokenAmount,
            filledTakerTokenAmount,
            paidMakerFee,
            paidTakerFee,
            keccak256(abi.encodePacked(order.makerToken, order.takerToken)),
            order.orderHash
        );
        return filledTakerTokenAmount;
    }

    /// @dev Fills the input order and also accepts trustlines token
    /// @param orderAddresses Array of order's maker, taker, makerToken, takerToken, and feeRecipient.
    /// @param orderValues Array of order's makerTokenAmount, takerTokenAmount, makerFee, takerFee, expirationTimestampInSec, and salt.
    /// @param fillTakerTokenAmount Desired amount of takerToken to fill.
    /// @param makerPath path of the payment of the maker token, if it is a trustlines token
    /// @param takerPath path of the payment of the taker token, if it is a trustlines token
    /// @param v ECDSA signature parameter v.
    /// @param r ECDSA signature parameters r.
    /// @param s ECDSA signature parameters s.
    /// @return filledTakerTokenAmount Total amount of takerToken filled in trade.
    function fillOrderTrustlines(
        address[5] memory orderAddresses,
        uint256[6] memory orderValues,
        uint256 fillTakerTokenAmount,
        address[] memory makerPath,
        address[] memory takerPath,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public returns (uint256 filledTakerTokenAmount) {
        Order memory order =
            Order({
                maker: orderAddresses[0],
                taker: orderAddresses[1],
                makerToken: orderAddresses[2],
                takerToken: orderAddresses[3],
                feeRecipient: orderAddresses[4],
                makerTokenAmount: orderValues[0],
                takerTokenAmount: orderValues[1],
                makerFee: orderValues[2],
                takerFee: orderValues[3],
                expirationTimestampInSec: orderValues[4],
                orderHash: getOrderHash(orderAddresses, orderValues)
            });

        require(
            order.taker == address(0) || order.taker == msg.sender,
            "Order taker must be message sender or the zero address."
        );
        require(
            order.makerTokenAmount > 0 &&
                order.takerTokenAmount > 0 &&
                fillTakerTokenAmount > 0,
            "Token amount of order maker, order taker, and fill taker must be positive."
        );
        require(
            isValidSignature(order.maker, order.orderHash, v, r, s),
            "The signature of the order is incorrect."
        );

        if (block.timestamp >= order.expirationTimestampInSec) {
            emit LogError(uint8(Errors.ORDER_EXPIRED), order.orderHash);
            return 0;
        }

        uint256 remainingTakerTokenAmount =
            order.takerTokenAmount -
                getUnavailableTakerTokenAmount(order.orderHash);
        filledTakerTokenAmount = min256(
            fillTakerTokenAmount,
            remainingTakerTokenAmount
        );
        if (filledTakerTokenAmount == 0) {
            emit LogError(
                uint8(Errors.ORDER_FULLY_FILLED_OR_CANCELLED),
                order.orderHash
            );
            return 0;
        }

        if (
            isRoundingError(
                filledTakerTokenAmount,
                order.takerTokenAmount,
                order.makerTokenAmount
            )
        ) {
            emit LogError(
                uint8(Errors.ROUNDING_ERROR_TOO_LARGE),
                order.orderHash
            );
            return 0;
        }

        uint256 filledMakerTokenAmount =
            getPartialAmount(
                filledTakerTokenAmount,
                order.takerTokenAmount,
                order.makerTokenAmount
            );
        filled[order.orderHash] =
            filled[order.orderHash] +
            filledTakerTokenAmount;

        if (makerPath.length > 0) {
            // Transfer in a Trustlines Network
            CurrencyNetworkInterface(order.makerToken).transferFrom(
                uint32(filledMakerTokenAmount), // TODO Overflow check
                MAX_FEE,
                makerPath,
                ""
            );
        } else {
            // Normal token transfer
            require(
                Token(order.makerToken).transferFrom(
                    order.maker,
                    msg.sender,
                    filledMakerTokenAmount
                ),
                "The maker token cannot be transferred from the maker to the taker."
            );
        }

        if (takerPath.length > 0) {
            // Transfer in a Trustlines Network
            CurrencyNetworkInterface(order.takerToken).transferFrom(
                uint32(filledTakerTokenAmount), // TODO Overflow check
                MAX_FEE,
                takerPath,
                ""
            );
        } else {
            require(
                Token(order.takerToken).transferFrom(
                    msg.sender,
                    order.maker,
                    filledTakerTokenAmount
                ),
                "The taker token cannot be transferred from the taker to the maker."
            );
        }

        emit LogFill(
            order.maker,
            msg.sender,
            order.feeRecipient,
            order.makerToken,
            order.takerToken,
            filledMakerTokenAmount,
            filledTakerTokenAmount,
            0,
            0,
            keccak256(abi.encodePacked(order.makerToken, order.takerToken)),
            order.orderHash
        );
        return filledTakerTokenAmount;
    }

    /// @dev Cancels the input order.
    /// @param orderAddresses Array of order's maker, taker, makerToken, takerToken, and feeRecipient.
    /// @param orderValues Array of order's makerTokenAmount, takerTokenAmount, makerFee, takerFee, expirationTimestampInSec, and salt.
    /// @param cancelTakerTokenAmount Desired amount of takerToken to cancel in order.
    /// @return Amount of takerToken cancelled.
    function cancelOrder(
        address[5] memory orderAddresses,
        uint256[6] memory orderValues,
        uint256 cancelTakerTokenAmount
    ) public returns (uint256) {
        Order memory order =
            Order({
                maker: orderAddresses[0],
                taker: orderAddresses[1],
                makerToken: orderAddresses[2],
                takerToken: orderAddresses[3],
                feeRecipient: orderAddresses[4],
                makerTokenAmount: orderValues[0],
                takerTokenAmount: orderValues[1],
                makerFee: orderValues[2],
                takerFee: orderValues[3],
                expirationTimestampInSec: orderValues[4],
                orderHash: getOrderHash(orderAddresses, orderValues)
            });

        require(
            order.maker == msg.sender,
            "The order maker has to match the message sender."
        );
        require(
            order.makerTokenAmount > 0 &&
                order.takerTokenAmount > 0 &&
                cancelTakerTokenAmount > 0,
            "Token amount of order maker, order taker, and cancel taker must be positive."
        );

        if (block.timestamp >= order.expirationTimestampInSec) {
            emit LogError(uint8(Errors.ORDER_EXPIRED), order.orderHash);
            return 0;
        }

        uint256 remainingTakerTokenAmount =
            order.takerTokenAmount -
                getUnavailableTakerTokenAmount(order.orderHash);
        uint256 cancelledTakerTokenAmount =
            min256(cancelTakerTokenAmount, remainingTakerTokenAmount);
        if (cancelledTakerTokenAmount == 0) {
            emit LogError(
                uint8(Errors.ORDER_FULLY_FILLED_OR_CANCELLED),
                order.orderHash
            );
            return 0;
        }

        cancelled[order.orderHash] =
            cancelled[order.orderHash] +
            cancelledTakerTokenAmount;

        emit LogCancel(
            order.maker,
            order.feeRecipient,
            order.makerToken,
            order.takerToken,
            getPartialAmount(
                cancelledTakerTokenAmount,
                order.takerTokenAmount,
                order.makerTokenAmount
            ),
            cancelledTakerTokenAmount,
            keccak256(abi.encodePacked(order.makerToken, order.takerToken)),
            order.orderHash
        );
        return cancelledTakerTokenAmount;
    }

    /*
     * Wrapper functions
     */

    /// @dev Fills an order with specified parameters and ECDSA signature, throws if specified amount not filled entirely.
    /// @param orderAddresses Array of order's maker, taker, makerToken, takerToken, and feeRecipient.
    /// @param orderValues Array of order's makerTokenAmount, takerTokenAmount, makerFee, takerFee, expirationTimestampInSec, and salt.
    /// @param fillTakerTokenAmount Desired amount of takerToken to fill.
    /// @param v ECDSA signature parameter v.
    /// @param r ECDSA signature parameters r.
    /// @param s ECDSA signature parameters s.
    function fillOrKillOrder(
        address[5] memory orderAddresses,
        uint256[6] memory orderValues,
        uint256 fillTakerTokenAmount,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public {
        require(
            fillOrder(
                orderAddresses,
                orderValues,
                fillTakerTokenAmount,
                false,
                v,
                r,
                s
            ) == fillTakerTokenAmount,
            "The specified amount was not filled entirely."
        );
    }

    /// @dev Synchronously executes multiple fill orders in a single transaction.
    /// @param orderAddresses Array of address arrays containing individual order addresses.
    /// @param orderValues Array of uint arrays containing individual order values.
    /// @param fillTakerTokenAmounts Array of desired amounts of takerToken to fill in orders.
    /// @param shouldThrowOnInsufficientBalanceOrAllowance Test if transfers will fail before attempting.
    /// @param v Array ECDSA signature v parameters.
    /// @param r Array of ECDSA signature r parameters.
    /// @param s Array of ECDSA signature s parameters.
    function batchFillOrders(
        address[5][] memory orderAddresses,
        uint256[6][] memory orderValues,
        uint256[] memory fillTakerTokenAmounts,
        bool shouldThrowOnInsufficientBalanceOrAllowance,
        uint8[] memory v,
        bytes32[] memory r,
        bytes32[] memory s
    ) public {
        for (uint256 i = 0; i < orderAddresses.length; i++) {
            fillOrder(
                orderAddresses[i],
                orderValues[i],
                fillTakerTokenAmounts[i],
                shouldThrowOnInsufficientBalanceOrAllowance,
                v[i],
                r[i],
                s[i]
            );
        }
    }

    /// @dev Synchronously executes multiple fillOrKill orders in a single transaction.
    /// @param orderAddresses Array of address arrays containing individual order addresses.
    /// @param orderValues Array of uint arrays containing individual order values.
    /// @param fillTakerTokenAmounts Array of desired amounts of takerToken to fill in orders.
    /// @param v Array ECDSA signature v parameters.
    /// @param r Array of ECDSA signature r parameters.
    /// @param s Array of ECDSA signature s parameters.
    function batchFillOrKillOrders(
        address[5][] memory orderAddresses,
        uint256[6][] memory orderValues,
        uint256[] memory fillTakerTokenAmounts,
        uint8[] memory v,
        bytes32[] memory r,
        bytes32[] memory s
    ) public {
        for (uint256 i = 0; i < orderAddresses.length; i++) {
            fillOrKillOrder(
                orderAddresses[i],
                orderValues[i],
                fillTakerTokenAmounts[i],
                v[i],
                r[i],
                s[i]
            );
        }
    }

    /// @dev Synchronously executes multiple fill orders in a single transaction until total fillTakerTokenAmount filled.
    /// @param orderAddresses Array of address arrays containing individual order addresses.
    /// @param orderValues Array of uint arrays containing individual order values.
    /// @param fillTakerTokenAmount Desired total amount of takerToken to fill in orders.
    /// @param shouldThrowOnInsufficientBalanceOrAllowance Test if transfers will fail before attempting.
    /// @param v Array ECDSA signature v parameters.
    /// @param r Array of ECDSA signature r parameters.
    /// @param s Array of ECDSA signature s parameters.
    /// @return Total amount of fillTakerTokenAmount filled in orders.
    function fillOrdersUpTo(
        address[5][] memory orderAddresses,
        uint256[6][] memory orderValues,
        uint256 fillTakerTokenAmount,
        bool shouldThrowOnInsufficientBalanceOrAllowance,
        uint8[] memory v,
        bytes32[] memory r,
        bytes32[] memory s
    ) public returns (uint256) {
        uint256 filledTakerTokenAmount = 0;
        for (uint256 i = 0; i < orderAddresses.length; i++) {
            require(
                orderAddresses[i][3] == orderAddresses[0][3],
                "The taker token must be the same for each order."
            );
            filledTakerTokenAmount =
                filledTakerTokenAmount +
                fillOrder(
                    orderAddresses[i],
                    orderValues[i],
                    fillTakerTokenAmount - filledTakerTokenAmount,
                    shouldThrowOnInsufficientBalanceOrAllowance,
                    v[i],
                    r[i],
                    s[i]
                );
            if (filledTakerTokenAmount == fillTakerTokenAmount) {
                break;
            }
        }
        return filledTakerTokenAmount;
    }

    /// @dev Synchronously cancels multiple orders in a single transaction.
    /// @param orderAddresses Array of address arrays containing individual order addresses.
    /// @param orderValues Array of uint arrays containing individual order values.
    /// @param cancelTakerTokenAmounts Array of desired amounts of takerToken to cancel in orders.
    function batchCancelOrders(
        address[5][] memory orderAddresses,
        uint256[6][] memory orderValues,
        uint256[] memory cancelTakerTokenAmounts
    ) public {
        for (uint256 i = 0; i < orderAddresses.length; i++) {
            cancelOrder(
                orderAddresses[i],
                orderValues[i],
                cancelTakerTokenAmounts[i]
            );
        }
    }

    /*
     * Constant public functions
     */

    /// @dev Calculates Keccak-256 hash of order with specified parameters.
    /// @param orderAddresses Array of order's maker, taker, makerToken, takerToken, and feeRecipient.
    /// @param orderValues Array of order's makerTokenAmount, takerTokenAmount, makerFee, takerFee, expirationTimestampInSec, and salt.
    /// @return Keccak-256 hash of order.
    function getOrderHash(
        address[5] memory orderAddresses,
        uint256[6] memory orderValues
    ) public view returns (bytes32) {
        return
            keccak256(
                abi.encodePacked(
                    address(this),
                    orderAddresses[0], // maker
                    orderAddresses[1], // taker
                    orderAddresses[2], // makerToken
                    orderAddresses[3], // takerToken
                    orderAddresses[4], // feeRecipient
                    orderValues[0], // makerTokenAmount
                    orderValues[1], // takerTokenAmount
                    orderValues[2], // makerFee
                    orderValues[3], // takerFee
                    orderValues[4], // expirationTimestampInSec
                    orderValues[5] // salt
                )
            );
    }

    /// @dev Verifies that an order signature is valid.
    /// @param signer address of signer.
    /// @param hash Signed Keccak-256 hash.
    /// @param v ECDSA signature parameter v.
    /// @param r ECDSA signature parameters r.
    /// @param s ECDSA signature parameters s.
    /// @return Validity of order signature.
    function isValidSignature(
        address signer,
        bytes32 hash,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public pure returns (bool) {
        return
            signer ==
            ecrecover(
                keccak256(
                    abi.encodePacked("\x19Ethereum Signed Message:\n32", hash)
                ),
                v,
                r,
                s
            );
    }

    /// @dev Checks if rounding error > 0.1%.
    /// @param numerator Numerator.
    /// @param denominator Denominator.
    /// @param target Value to multiply with numerator/denominator.
    /// @return Rounding error is present.
    function isRoundingError(
        uint256 numerator,
        uint256 denominator,
        uint256 target
    ) public pure returns (bool) {
        uint256 remainder = mulmod(target, numerator, denominator);
        if (remainder == 0) {
            return false; // No rounding error.
        }

        uint256 errPercentageTimes1000000 =
            (remainder * 1000000) / (numerator * target);
        return errPercentageTimes1000000 > 1000;
    }

    /// @dev Calculates partial value given a numerator and denominator.
    /// @param numerator Numerator.
    /// @param denominator Denominator.
    /// @param target Value to calculate partial of.
    /// @return Partial value of target.
    function getPartialAmount(
        uint256 numerator,
        uint256 denominator,
        uint256 target
    ) public pure returns (uint256) {
        return (numerator * target) / denominator;
    }

    /// @dev Calculates the sum of values already filled and cancelled for a given order.
    /// @param orderHash The Keccak-256 hash of the given order.
    /// @return Sum of values already filled and cancelled.
    function getUnavailableTakerTokenAmount(bytes32 orderHash)
        public
        view
        returns (uint256)
    {
        return filled[orderHash] + cancelled[orderHash];
    }

    /// @dev Get token balance of an address.
    /// @dev The called token contract may attempt to change state, but will not be able to due to an added gas limit.
    /// @param token Address of token.
    /// @param owner Address of owner.
    /// @return Token balance of owner.
    function getBalance(address token, address owner)
        internal
        view
        returns (uint256)
    {
        return Token(token).balanceOf{gas: EXTERNAL_QUERY_GAS_LIMIT}(owner); // Limit gas to prevent reentrancy
    }

    /// @dev Get allowance of token given to TokenTransferProxy by an address.
    /// @dev The called token contract may attempt to change state, but will not be able to due to an added gas limit.
    /// @param token Address of token.
    /// @param owner Address of owner.
    /// @return Allowance of token given to TokenTransferProxy by owner.
    function getAllowance(address token, address owner)
        internal
        view
        returns (uint256)
    {
        return
            Token(token).allowance{gas: EXTERNAL_QUERY_GAS_LIMIT}(
                owner,
                address(this)
            ); // Limit gas to prevent reentrancy
    }

    function min256(uint256 a, uint256 b) internal pure returns (uint256) {
        return a < b ? a : b;
    }
}

// SPDX-License-Identifier: MIT
