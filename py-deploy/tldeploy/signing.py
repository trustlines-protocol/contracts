from typing import List, Tuple, Union

from eth_keys import keys
from eth_keys.exceptions import BadSignature
from web3 import Web3


def eth_sign(hash: bytes, key: bytes):
    v, r, s = (
        keys.PrivateKey(key)
        .sign_msg_hash(Web3.sha3(b"\x19Ethereum Signed Message:\n32" + hash))
        .vrs
    )
    if v < 27:
        v += 27
    r = r.to_bytes(32, byteorder="big")
    s = s.to_bytes(32, byteorder="big")
    return v, r, s


def eth_validate(
    msg_hash: bytes,
    vrs: Tuple[Union[int, bytes], Union[int, bytes], Union[int, bytes]],
    address: str,
):
    v, r, s = vrs
    if isinstance(v, bytes):
        v = int.from_bytes(v, byteorder="big")
    if isinstance(r, bytes):
        r = int.from_bytes(r, byteorder="big")
    if isinstance(s, bytes):
        s = int.from_bytes(s, byteorder="big")
    if v >= 27:
        v -= 27
    sig = keys.Signature(vrs=(v, r, s))
    try:
        pubkey = sig.recover_public_key_from_msg_hash(
            Web3.sha3(b"\x19Ethereum Signed Message:\n32" + msg_hash)
        )
        return pubkey.to_checksum_address() == address
    except BadSignature:
        return False


def priv_to_pubkey(key: bytes):
    return keys.PrivateKey(key).public_key.to_checksum_address()


def solidity_keccak(abi_types: List, values: List) -> bytes:
    return Web3.solidityKeccak(abi_types, values)


def sign_msg_hash(hash: bytes, key: keys.PrivateKey) -> bytes:
    return key.sign_msg_hash(hash).to_bytes()
