from eth_keys import keys
from eth_keys.exceptions import BadSignature
from eth_utils import (
    decode_hex,
    keccak,
    is_0x_prefixed,
)


def pack(*args) -> bytes:
    """
    Simulates Solidity's keccak256 packing. Integers can be passed as tuples where the second tuple
    element specifies the variable's size in bits, e.g.:
    keccak256((5, 32))
    would be equivalent to Solidity's
    keccak256(uint32(5))
    Default size is 256.
    """
    def format_int(value, size):
        assert isinstance(value, int)
        assert isinstance(size, int)
        if value >= 0:
            return decode_hex('{:x}'.format(value).zfill(size // 4))
        else:
            return decode_hex('{:x}'.format((1 << size) + value))

    msg = b''
    for arg in args:
        assert arg is not None
        if isinstance(arg, bytes):
            msg += arg
        elif isinstance(arg, str):
            if is_0x_prefixed(arg):
                msg += decode_hex(arg)
            else:
                msg += arg.encode()
        elif isinstance(arg, bool):
            msg += format_int(int(arg), 8)
        elif isinstance(arg, int):
            msg += format_int(arg, 256)
        elif isinstance(arg, tuple):
            msg += format_int(arg[0], arg[1])
        else:
            raise ValueError('Unsupported type: {}.'.format(type(arg)))

    return msg


def keccak256(*args) -> bytes:
    return keccak(pack(*args))


def eth_sign(hash, key):
    v, r, s = keys.PrivateKey(key).sign_msg_hash(keccak256(b'\x19Ethereum Signed Message:\n32', hash)).vrs
    if v < 27:
        v += 27
    r = r.to_bytes(32, byteorder='big')
    s = s.to_bytes(32, byteorder='big')
    return v, r, s


def eth_validate(msg_hash, vrs, address):
    v, r, s = vrs
    if isinstance(v, bytes):
        v = int.from_bytes(r, byteorder='big')
    if isinstance(r, bytes):
        r = int.from_bytes(r, byteorder='big')
    if isinstance(s, bytes):
        s = int.from_bytes(s, byteorder='big')
    if v >= 27:
        v -= 27
    sig = keys.Signature(vrs=(v, r, s))
    try:
        pubkey = sig.recover_public_key_from_msg_hash(keccak256(b'\x19Ethereum Signed Message:\n32', msg_hash))
        return pubkey.to_checksum_address() == address
    except BadSignature:
        return False


def priv_to_pubkey(key):
    return keys.PrivateKey(key).public_key.to_checksum_address()
