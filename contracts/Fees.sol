pragma solidity ^0.4.0;

import "./lib/SafeMath.sol";
import "./Trustline.sol";

library Fees {

    using SafeMath for int64;
    using SafeMath for int256;
    using SafeMath for uint16;
    using SafeMath for uint32;
    using SafeMath for uint192;

    /*
     * @notice The network fee is payable by the inititator of a transfer.
     * @notice It is tracked in the outgoing account to avoid updating a user global storage slot.
     * @notice The system fee is splitted between the onboarders and the investors.
     * @param sender User wishing to send funds to receiver, incurring the fee
     * @param receiver User receiving the funds
     * @param value Amount of tokens being transferred
     */
    function applyNetworkFee(address _sender, address _receiver, int48 _value, uint16 _network_fee_divisor) internal constant returns (uint16 fee) {
        fee = uint16(calculateNetworkFee(_value, _network_fee_divisor));
    }

    /*
     * @notice Calculates the system fee from the value being transferred
     * @param value being transferred
     */
    function calculateNetworkFee(int64 _value, uint16 _network_fee_divisor) internal constant returns (int64) {
        return int64(_value.div(_network_fee_divisor));
    }

    /*
     * @notice The fees deducted from the value while being transferred from second hop onwards in the mediated transfer
     */
    function deductedTransferFees(int64 _balance, address _sender, address _receiver, uint32 _value, uint16 _capacity_fee_divisor, uint16 _imbalance_fee_divisor) internal constant returns (uint16) {
        return capacityFee(_value, _capacity_fee_divisor).add16(imbalanceFee(_balance, _sender, _receiver, _value, _imbalance_fee_divisor));
    }

    /*
     * @notice reward for providing the edge with sufficient capacity
     * @notice beneficiary: sender (because receiver will receive if he's the next hop)
     */
    function capacityFee(uint32 _value, uint16 _capacity_fee_divisor) internal constant returns (uint16) {
        return uint16(_value.div32(_capacity_fee_divisor));
    }

    /*
     * @notice penality for increasing account imbalance
     * @notice beneficiary: sender (because receiver will receive if he's the next hop)
     * @notice NOTE: It should also incorporate the interest as users will favor being indebted in
     */
    function imbalanceFee(int64 _balanceAB, address _sender, address _receiver, uint32 _value, uint16 _imbalance_fee_divisor) internal constant returns (uint16) {
        uint32 addedImbalance = _value;
        int64 newBalance = 0;
        if (_balanceAB > 0) {
            // positive hence receiver indebted to sender so if the newBalance is smaller then zero we introduce imbalance
            newBalance = _balanceAB.sub64(_value);
            if (newBalance < 0) {
                addedImbalance = uint32(-newBalance);
            }
        } else {
            newBalance = _balanceAB.add64(_value);
            if (newBalance > 0) {
                addedImbalance = uint32(newBalance);
            }
        }
        return uint16(addedImbalance / _imbalance_fee_divisor);
    }

}
