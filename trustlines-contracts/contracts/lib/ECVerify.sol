pragma solidity ^0.4.11;


//
// The new assembly support in Solidity makes writing helpers easy.
// Many have complained how complex it is to use `ecrecover`, especially in conjunction
// with the `eth_sign` RPC call. Here is a helper, which makes that a matter of a single call.
//
// Sample input parameters:
// (with v=0)
// "0x47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad",
// "0xaca7da997ad177f040240cdccf6905b71ab16b74434388c3a72f34fd25d6439346b2bac274ff29b48b3ea6e2d04c1336eaceafda3c53ab483fc3ff12fac3ebf200",
// "0x0e5cb767cce09a7f3ca594df118aa519be5e2b5a"
//
// (with v=1)
// "0x47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad",
// "0xdebaaa0cddb321b2dcaaf846d39605de7b97e77ba6106587855b9106cb10421561a22d94fa8b8a687ff9c911c844d1c016d1a685a9166858f9c7c1bc85128aca01",
// "0x8743523d96a1b2cbe0c6909653a56da18ed484af"
//
// (The hash is a hash of "hello world".)
//
// Written by Alex Beregszaszi (@axic), use it under the terms of the MIT license.
//
library ECVerify {

    function saferECRecover(
        bytes32 hash,
        uint8 v,
        bytes32 r,
        bytes32 s
    )
        internal
        returns (
            bool,
            address)
    {
        bool ret;
        address addr;

        assembly {
            let size := mload(0x40)
            mstore(size, hash)
            mstore(add(size, 32), v)
            mstore(add(size, 64), r)
            mstore(add(size, 96), s)

            ret := call(3000, 1, 0, size, 128, size, 32)
            addr := mload(size)
        }

        return (ret, addr);
    }

    function ecrecovery(bytes32 hash, bytes sig) internal returns (bool, address) {
        bytes32 r;
        bytes32 s;
        uint8 v;

        if (sig.length != 65)
            return (false, 0);

        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))

            v := byte(0, mload(add(sig, 96)))
        }

        if (v < 27)
            v += 27;

        if (v != 27 && v != 28)
            return (false, 0);

        return saferECRecover(
            hash,
            v,
            r,
            s);
    }

    function ecverify(bytes32 hash, bytes sig) internal returns (address addr) {
        bool ret;
        (ret, addr) = ecrecovery(hash, sig);
    }

}
