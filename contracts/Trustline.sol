pragma solidity ^0.4.0;

contract Trustline {

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

}