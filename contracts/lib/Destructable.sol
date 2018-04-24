pragma solidity ^0.4.11;

import "./Ownable.sol";

/*
 * Destructable
 *
 * Base contract that can be killed.
 */


contract Destructable is Ownable {

    function destruct() external onlyOwner {
        selfdestruct(owner);
    }
}

