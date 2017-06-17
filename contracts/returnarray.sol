pragma solidity ^0.4.4;
contract Test {

    mapping (address => address[]) peers;

    function addPeer(address peer) {
        uint len = peers[tx.origin].push(peer);
    }

    function numPeers(address user) constant returns (uint) {
        return peers[user].length;
    }

    function getPeers(address user) constant returns (address[]) {
        return peers[user];
    }
}
