#! pytest

from eth_utils import to_checksum_address
from tldeploy.signing import eth_validate, eth_sign


def test_eth_validate(accounts, account_keys):
    address = accounts[0]
    key = account_keys[0].to_bytes()

    msg_hash = bytes(32)
    vrs = eth_sign(msg_hash, key)
    assert eth_validate(msg_hash, vrs, to_checksum_address(address))


def test_eth_validate_fail(accounts, account_keys):
    address = accounts[0]
    key = account_keys[0].to_bytes()

    msg_hash1 = bytes(32)
    msg_hash2 = (123).to_bytes(32, byteorder='big')
    vrs = eth_sign(msg_hash1, key)
    assert not eth_validate(msg_hash2, vrs, to_checksum_address(address))


def test_eth_validate_fail2(accounts, account_keys):
    address = accounts[0]

    msg_hash = bytes(32)
    v = 27
    r = 18
    s = 2748
    assert not eth_validate(msg_hash, (v, r, s), to_checksum_address(address))
