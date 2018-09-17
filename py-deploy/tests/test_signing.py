from ethereum import tester
from eth_utils import to_checksum_address
from tlcontracts.signing import eth_validate, eth_sign


def test_eth_validate():
    msg_hash = bytes(32)
    vrs = eth_sign(msg_hash, tester.k0)
    assert eth_validate(msg_hash, vrs, to_checksum_address(tester.a0))


def test_eth_validate_fail():
    msg_hash1 = bytes(32)
    msg_hash2 = (123).to_bytes(32, byteorder='big')
    vrs = eth_sign(msg_hash1, tester.k0)
    assert not eth_validate(msg_hash2, vrs, to_checksum_address(tester.a0))


def test_eth_validate_fail2():
    msg_hash = bytes(32)
    v = 27
    r = 18
    s = 2748
    assert not eth_validate(msg_hash, (v, r, s), to_checksum_address(tester.a0))
