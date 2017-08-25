pragma solidity ^0.4.11;

import "./Trustline.sol";
import "./lib/Owned.sol";

contract EternalStorage is Owned {

    mapping(bytes32 => Trustline.Account) public accounts;

    function EternalStorage(address _adminKey) Owned(_adminKey) {

    }

    function setAccount(address _A, address _B, uint32 clAB, uint32 clBA, uint16 iAB, uint16 iBA, uint16 fA, uint16 fB, uint16 mtime, int64 balance) onlyOwner external
    {
        Trustline.Account account = accounts[uniqueIdentifier(_A, _B)];
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
        Trustline.Account account = accounts[uniqueIdentifier(_A, _B)];
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


    function uniqueIdentifier(address _A, address _B) internal constant returns (bytes32) {
        require(_A != _B);
        if (_A < _B) {
            return sha3(_A, _B);
        } else if (_A > _B) {
            return sha3(_B, _A);
        }
    }
}
