import binascii
import bitcoin
from ethereum import utils
from ethereum.utils import sha3
from secp256k1 import PrivateKey


def eth_privtoaddr(priv) -> str:
    pub = bitcoin.encode_pubkey(bitcoin.privtopub(priv), 'bin_electrum')
    return "0x" + binascii.hexlify(sha3(pub)[12:]).decode("ascii")


def sign(data: bytes, private_key_seed_ascii: str):
    pk = PrivateKey(private_key_seed_ascii, raw=True)
    signature = pk.ecdsa_recoverable_serialize(pk.ecdsa_sign_recoverable(data, raw=True))
    signature = signature[0] + utils.bytearray_to_bytestr([signature[1]])
    return signature, eth_privtoaddr(private_key_seed_ascii)


def check(data: bytes, pk: bytes):
    return sign(data, pk)


if __name__ == "__main__":
    valueFromSha3Of = "0x847db6e753ecd05088c44ff58afe6beb093c70710032e267844ac49def3746a9"
    valueFromSha3OfAsBytes = binascii.unhexlify(valueFromSha3Of[2:])
    print(check(valueFromSha3OfAsBytes,
                binascii.unhexlify("9a4b1eab6a8192265147a6fffa0aa592673e039f5b4f33734e8f5db93b6c53cf")))
