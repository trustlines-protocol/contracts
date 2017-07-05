pragma solidity ^0.4.0;

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

    using SafeMath for int48;
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
    function applyInterest(Trustline.Account storage _account, uint16 _mtime) internal {
        // Check whether request came from msg.sender otherwise anyone can call and change the mtime of the account
        if (_mtime == _account.mtime)
            return;
        int elapsed = _mtime.sub16(_account.mtime);
        uint16 interestByte = 0;
        if (_account.balanceAB > 0) { // netted balance, value B owes to A(if positive)
            interestByte = _account.interestAB; // interest rate set by A for debt of B
        } else {
            interestByte = _account.interestBA; // interest rate set by B for debt of A
        }
        int interest = calculateInterest(interestByte, _account.balanceAB).mul(elapsed);
        _account.mtime = _mtime;
        _account.balanceAB += int48(interest);
    }

    /*
     * @notice returns the linear interest on the imbalance since last account update.
     * @notice negative if A is indebted to B, positive otherwise
     */
    function occurredInterest(Trustline.Account storage _account, uint16 _mtime) public returns (int) {
        int elapsed = _mtime - _account.mtime;
        uint16 interest = 0;
        if (_account.balanceAB > 0) { // netted balance, value B owes to A(if positive)
            interest = _account.interestAB; // interest rate set by A for debt of B
        } else {
            interest = _account.interestBA; // interest rate set by B for debt of A
        }
        return calculateInterest(interest, _account.balanceAB).mul(elapsed);
    }

    /*
     * @notice Calculates the interest from the byte representation of annual interest rate
     * @param interest byte representation of annual interest rate
     * @param balance current balance value in the account
     */
    function calculateInterest(int _interest, int _balance) public returns (int) {
        if(_interest == 0 && _interest > 255)
            return 0;
        return _balance.div(_interest.mul(256));
    }

    // Only test functions here will be removed in the final release
    function occurredInterestTest(Trustline.Account storage _account, uint16 _mtime) public returns (int, int) {
        int elapsed = _mtime.sub16(_account.mtime);
        uint16 di = 0;
        if(_account.balanceAB > 0){
            di = _account.interestAB;
        }else{
            di = _account.interestBA;
        }
        return (calculateInterest(di, _account.balanceAB), elapsed);
    }

    /*
     * @notice This function returns the annual interest rate as byte
     * @dev need to converted to know the actual value of annual interest rate
     * @param Ethereum addresses of A and B
     * @return Interest rate set by A for the debt of B
     */
    function getInterestRate(Trustline.Account storage _account, address _A, address _B) constant returns (uint256 interestrate) {
        if (_A < _B) {
            return _account.interestAB;
        } else {
            return _account.interestBA;
        }
    }


}