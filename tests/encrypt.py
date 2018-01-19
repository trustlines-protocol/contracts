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
