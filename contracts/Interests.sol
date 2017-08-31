pragma solidity ^0.4.11;

import "./Trustline.sol";
import "./lib/SafeMath.sol";

/*
 * Interests
 *
 * Calculates all interests for the path of a transaction in CurrencyNetwork.
 * Fees can be set at creation of CurrencyNetwork, and can be omitted (default).
 *
 */
library Interests {

    using SafeMath for int64;
    using SafeMath for int256;
    using SafeMath for uint16;
    using SafeMath for uint32;

    /*
     * @notice With every update of the account the interest inccurred
     * @notice since the last update is calculated and added to the balance.
     * @notice The interest is calculated linearily. Effective compounding depends on frequent updates.
     * @param sender User wishing to send funds to receiver, incurring the interest(interest gets added to the balance)
     * @param receiver User receiving the funds, the beneficiary of the interest
     * @param mtime the current day since system start
     */
    function occurredInterest(int64 _balance, uint16 _interest, uint16 _timediff) internal returns (int64 interest){
        // Check whether request came from msg.sender otherwise anyone can call and change the mtime of the account
        if ((_timediff == 0) || (_interest == 0)) {
            return;
        }
        interest = int64(_balance.div(_interest.mul16(256)).mul(_timediff));
    }

}
