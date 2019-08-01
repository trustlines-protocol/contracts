pragma solidity ^0.5.8;

import "./Ownable.sol";

/*
 * Destructable
 *
 * Base contract that can be killed.
 */


contract Destructable is Ownable {

    function destruct() external onlyOwner {
        selfdestruct(address(uint160(owner)));
    }
}
