pragma solidity ^0.4.25;


contract Mock {

    event TestFunctionCalled(address from, uint256 value, bytes data);

    function Mock(){

    }

    function testFunction(bytes data){
        address from = msg.sender;
        uint256 value = msg.value;
        emit TestFunctionCalled(from, value, data);
    }
}
