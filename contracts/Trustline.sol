pragma solidity ^0.4.0;

library Trustline {

    // for accounting balance and trustline between two users introducing fees and interests
    // currently uses 208 bits, 48 remaining
    struct Account {
        // A < B (A is the lower address)
        uint16 interestAB;          //  interest rate set by A for debt of B
        uint16 interestBA;          //  interest rate set by B for debt of A

        uint16 mtime;               //  last modification time

        uint16 feesOutstandingA;    //  fees outstanding by A
        uint16 feesOutstandingB;    //  fees outstanding by B

        uint32 creditlineAB;        //  creditline given by A to B, always positive
        uint32 creditlineBA;        //  creditline given by B to A, always positive

        int64 balanceAB;            //  balance between A and B, A->B (x(-1) for B->A)
    }

    /*
     * @notice hash to look up the account between A and B in accounts
     * @dev hash to look up the account between A and B in accounts
     * @param Two Ethereum addresses in the account pair
     */
    function keyBalance(address _A, address _B) internal constant returns (bytes32) {
        if (_A < _B) {
            return sha3(_A, _B);
        }
        else if (_A > _B) {
            return sha3(_B, _A);
        }
        else {
            // A == B not allowed
            throw;
        }
    }

    // load balance from storage
    function loadBalance(Account storage _self, address _A, address _B) internal constant returns (int64) {
        int64 balance;
        balance = _self.balanceAB;
        if (_A > _B) {
            balance = - balance;
        }
        return balance;
    }

    // store balance to storage
    function storeBalance(Account storage _self, address _A, address _B, int64 _balance) internal {
        if (_A < _B) {
            _self.balanceAB = _balance;
        }
        else {
            _self.balanceAB = - _balance;
        }
    }

    // load the Creditline given from _A to _B from storage
    function loadCreditline(Account storage _self, address _A, address _B) internal constant returns (uint32 creditline) {
        if (_A < _B) {
             creditline = _self.creditlineAB;
        } else {
             creditline = _self.creditlineBA;
        }
    }

    // store the Creditline given from _A to _B
    function storeCreditline(Account storage _self, address _A, address _B, uint32 _creditline) internal {
        if (_A < _B) {
            // cannot set balance below balance
            if (_self.balanceAB > _creditline) {
                throw;
            }
            _self.creditlineAB = _creditline;
        } else {
            if (- _self.balanceAB > _creditline) {
                throw;
            }
            _self.creditlineBA = _creditline;
        }
    }

}