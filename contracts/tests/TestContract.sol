pragma solidity ^0.5.8;

import "../currency-network/DebtTracking.sol";


// Test contract used for testing identity contract meta transaction features
contract TestContract is DebtTracking {

    event TestEvent(
        address from,
        uint256 value,
        bytes data,
        int argument
    );

    function increaseDebt(address creditor, uint value) external {
    }

    function getDebt(address, address) public view returns (int) {
        return 0;
    }

    function testFunction(int argument) public payable {
        address from = msg.sender;
        uint256 value = msg.value;
        bytes memory data = msg.data;
        emit TestEvent(
            from,
            value,
            data,
            argument
        );
    }

    function fails() public pure {
        revert("This will just always fail");
    }
}
