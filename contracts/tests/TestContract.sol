pragma solidity ^0.4.25;


contract TestContract {

    event TestEvent(
        address from,
        uint256 value,
        bytes data,
        int argument
    );

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

    function fails() public {
        revert();
    }
}
