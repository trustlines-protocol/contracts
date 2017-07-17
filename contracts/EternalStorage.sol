pragma solidity ^0.4.0;

import "./Trustline.sol";
import "./lib/Owned.sol";

contract EternalStorage is Owned {

    mapping(bytes32 => Trustline.Account) public accounts;

    function authorize(address user) onlyOwner {
        owner = user;
    }

    function setAccount(address _A, address _B, uint32 clAB, uint32 clBA, uint16 iAB, uint16 iBA, uint16 fA, uint16 fB, uint16 mtime, int64 balance) onlyOwner
    {
        Trustline.Account storage account = accounts[uniqueIdentifier(_A, _B)];
        if (_A < _B) {
            // View of the Account if the address A < B
            account.creditlineAB = clAB;
            account.creditlineBA = clBA;
            account.interestAB = iAB;
            account.interestBA = iBA;
            account.feesOutstandingA = fA;
            account.feesOutstandingB = fB;
            account.mtime = mtime;
            account.balanceAB = balance;
        } else {
            // View of the account if Address A > B
            account.creditlineBA = clAB;
            account.creditlineAB = clBA;
            account.interestBA = iAB;
            account.interestAB = iBA;
            account.feesOutstandingB = fA;
            account.feesOutstandingA = fB;
            account.mtime = mtime;
            account.balanceAB = -balance;
         }
    }

    function getAccount(address _A, address _B) public constant returns (int, int, int, int, int, int, int, int)
    {
        Trustline.Account storage account = accounts[uniqueIdentifier(_A, _B)];
        if (_A < _B) {
            // View of the Account if the address A < B
            return (account.creditlineAB,
                    account.creditlineBA,
                    account.interestAB,
                    account.interestBA,
                    account.feesOutstandingA,
                    account.feesOutstandingB,
                    account.mtime,
                    account.balanceAB);
        } else {
            // View of the account if Address A > B
            return (account.creditlineBA,
                    account.creditlineAB,
                    account.interestBA,
                    account.interestAB,
                    account.feesOutstandingB,
                    account.feesOutstandingA,
                    account.mtime,
                    - account.balanceAB);
         }
    }

    function getCreditline(address _A, address _B) public constant returns (uint32 creditline) {
        if (_A < _B) {
            creditline = accounts[uniqueIdentifier(_A, _B)].creditlineAB;
        } else {
            creditline = accounts[uniqueIdentifier(_A, _B)].creditlineBA;
        }
    }

    function getInterestRate(address _A, address _B) public constant returns (uint16 interest) {
        if (_A < _B) {
            interest = accounts[uniqueIdentifier(_A, _B)].interestAB;
        } else {
            interest = accounts[uniqueIdentifier(_A, _B)].interestBA;
        }
    }

    function getOutstandingFees(address _A, address _B) public constant returns (uint16 fees) {
        if (_A < _B) {
            fees = accounts[uniqueIdentifier(_A, _B)].feesOutstandingA;
        } else {
            fees = accounts[uniqueIdentifier(_A, _B)].feesOutstandingB;
        }
    }

    function updateOutstandingFees(address _A, address _B, uint16 fees) public {
        if (_A < _B) {
            accounts[uniqueIdentifier(_A, _B)].feesOutstandingA += fees;
        } else {
            accounts[uniqueIdentifier(_A, _B)].feesOutstandingB += fees;
        }
    }

    function getBalance(address _A, address _B) public constant returns (int64 balance) {
        if (_A < _B) {
            balance = accounts[uniqueIdentifier(_A, _B)].balanceAB;
        } else {
            balance = - accounts[uniqueIdentifier(_A, _B)].balanceAB;
        }
    }

    function getLastModification(address _A, address _B) public constant returns (uint16 mtime) {
        mtime = accounts[uniqueIdentifier(_A, _B)].mtime;
    }

    // store balance to storage
    function storeBalance(address _A, address _B, int64 _balance) public {
        if (_A < _B) {
            accounts[uniqueIdentifier(_A, _B)].balanceAB = _balance;
        } else {
            accounts[uniqueIdentifier(_A, _B)].balanceAB = -_balance;
        }
    }

    // store balance to storage
    function addToBalance(address _A, address _B, int64 _diff) public {
        accounts[uniqueIdentifier(_A, _B)].balanceAB += _diff;
    }

    function storeCreditline(address _A, address _B, uint32 _creditline) public {
        Trustline.Account storage account = accounts[uniqueIdentifier(_A, _B)];
        if (_A < _B) {
            assert(account.balanceAB <= _creditline);
            account.creditlineAB = _creditline;
        } else {
            assert(- account.balanceAB <= _creditline);
            account.creditlineBA = _creditline;
        }
    }

    function updateInterest(address _creditor, address _debtor, uint16 _ir) public {
        if (_creditor < _debtor) {
            accounts[uniqueIdentifier(_creditor, _debtor)].interestAB = _ir;
        } else {
            accounts[uniqueIdentifier(_creditor, _debtor)].interestBA = _ir;
        }
    }

    function uniqueIdentifier(address _A, address _B) internal constant returns (bytes32) {
        if (_A < _B) {
            return sha3(_A, _B);
        } else if (_A > _B) {
            return sha3(_B, _A);
        } else {
            // A == B not allowed
            throw;
        }
    }

}