pragma solidity ^0.5.8;

import "./Ownable.sol";

/*
 * Destructable
 *
 * Base contract that can be killed.
 */


contract Destructable is Ownable {

    function destruct() external onlyOwner {
        // We use address(uint160(owner)) to convert owner from address to address payable
        selfdestruct(address(uint160(owner)));
    }
}
