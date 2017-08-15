import pytest
from ethereum import tester
import encrypt
import binascii, sys
from Crypto.PublicKey import RSA
from populus.utils.wait import wait_for_transaction_receipt
import ipfsapi
from web3.utils.compat import (
    Timeout,
)

@pytest.fixture()
def user_contract(chain, web3):
    UserInformation = chain.provider.get_contract_factory('UserInformation')
    deploy_txn_hash = UserInformation.deploy(args=[web3.eth.accounts[0]])
    userInformationAddr = chain.wait.for_contract_address(deploy_txn_hash)
    user_contract = UserInformation(address=userInformationAddr)
    return user_contract


def wait(transfer_filter):
    with Timeout(30) as timeout:
        while not transfer_filter.get(False):
            timeout.sleep(2)


def print_logs(contract, event, name=''):
    transfer_filter_past = contract.pastEvents(event)
    past_events = transfer_filter_past.get()
    if len(past_events):
        print('--(', name, ') past events for ', event, past_events)

    transfer_filter = contract.on(event)
    events = transfer_filter.get()
    if len(events):
        print('--(', name, ') events for ', event, events)

    transfer_filter.watch(lambda x: print('--(', name, ') event ', event, x['args']))


def test_user_public_key(user_contract, web3):
    key = encrypt.createKey()
    binPubKey1 = key.publickey().exportKey('DER')
    print(sys.getsizeof(binPubKey1))
    user_contract.transact().setPubKey(binPubKey1)
    binPubKey2 = user_contract.call().userPubkey(web3.eth.accounts[0])
    print(binPubKey2)
    pubKeyObj = RSA.importKey(binPubKey2)
    enc_data = encrypt.encrypt(pubKeyObj, 'Hello there!')
    print(encrypt.decrypt(enc_data, key))


def test_ipfs_integration(user_contract, web3):
    # create new private key
    key = encrypt.createKey()
    # get public key from private key
    binPubKey1 = key.publickey().exportKey('DER')
    # set public key for user in blockchain
    user_contract.transact().setPubKey(binPubKey1)
    # retrieve public key for user
    binPubKey2 = user_contract.call().userPubkey(web3.eth.accounts[0])
    # import public key from blockchain
    pubKeyObj = RSA.importKey(binPubKey2)
    # encrypt message with public key of user
    enc_data = encrypt.encrypt(pubKeyObj, 'Last Night...')

    # connect to locally running IPFS daemon
    api = ipfsapi.connect('127.0.0.1', 5001)
    # add encrypted message
    res = api.add_bytes(enc_data)
    print("\n\nIPFS_HASH_CREATE:\t", res)

    # filter for YouHaveMail events on contract
    transfer_filter = user_contract.on("YouHaveMail")
    user_contract.transact().sendMessage(web3.eth.accounts[1], res)
    wait(transfer_filter)
    log_entries = transfer_filter.get()

    # extract ipfsHash from event
    res = log_entries[0]['args']['_ipfsHash']
    print("IPFS_HASH_EVENT:\t", res)
    # get stored encrypted message from IPFS
    ret = api.cat(res)
    print("IPFS_HASH_DATA:\t\t", ret)
    # decrypt message with private key of user
    print("IFPS_DATA_DECR:\t\t", encrypt.decrypt(ret, key))
