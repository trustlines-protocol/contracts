from Crypto.PublicKey import RSA
from Crypto import Random
import binascii

def createKey():
    random_generator = Random.new().read
    return RSA.generate(1024, random_generator)


def encrypt(pub_key, data):
    return pub_key.encrypt(data.encode("utf-8"), data)[0]


def decrypt(data, key):
    return key.decrypt(data)


def bin2hex(binStr):
    return binascii.hexlify(binStr)


def hex2bin(hexStr):
    return binascii.unhexlify(hexStr)


if __name__ == "__main__":
    key = createKey()
    public_key = key.publickey()
    enc_data = encrypt(public_key, "hello there!")
    print(decrypt(enc_data, key))
    

"0x5e72914535f202659083db3a02c984188fa26e9f",100,["0x5e","0x72", "0x91", "0x45", "0x35", "0xf2", "0x02", "0x65", "0x90", "0x83", "0xdb", "0x3a", "0x02", "0xc9", "0x84", "0x18", "0x8f", "0xa2", "0x6e", "0x9f"]