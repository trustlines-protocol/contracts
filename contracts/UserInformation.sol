pragma solidity ^0.4.0;


contract UserInformation {

    mapping (address => bytes) public userPubkey;

    event YouHaveMail(address _receiver, bytes _ipfsHash);

    function sendMessage(address _receiver, bytes _ipfsHash) public {
        YouHaveMail(_receiver, _ipfsHash);
    }

    function setPubKey(bytes key) public {
        userPubkey[msg.sender] = key;
    }

}