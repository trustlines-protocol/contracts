pragma solidity ^0.5.8;


/*
* Contract that is working with ERC223 tokens
*/

interface ContractReceiver {

    function tokenFallback(address _from, uint _value, bytes calldata _data) external;

}
