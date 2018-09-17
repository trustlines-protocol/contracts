import pytest
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider
from eth_utils import to_checksum_address, encode_hex
import eth_tester


@pytest.fixture()
def tester():
    """ethereum.tools.tester compatible class"""

    class tester:
        pass

    t = tester()
    t.k0 = b"\x04HR\xb2\xa6p\xad\xe5@~x\xfb(c\xc5\x1d\xe9\xfc\xb9eB\xa0q\x86\xfe:\xed\xa6\xbb\x8a\x11m"
    t.a0 = b"\x82\xa9x\xb3\xf5\x96*[\tW\xd9\xee\x9e\xefG.\xe5[B\xf1"
    return t


@pytest.fixture(scope="session")
def ethereum_tester_session():
    """Returns an instance of an Ethereum tester"""
    tester = eth_tester.EthereumTester(eth_tester.PyEVMBackend())
    k0 = b"\x04HR\xb2\xa6p\xad\xe5@~x\xfb(c\xc5\x1d\xe9\xfc\xb9eB\xa0q\x86\xfe:\xed\xa6\xbb\x8a\x11m"
    a0 = tester.add_account(encode_hex(k0))
    faucet = tester.get_accounts()[0]
    tester.send_transaction(
        {"from": faucet, "to": to_checksum_address(a0), "gas": 21000, "value": 10000000}
    )
    return tester


@pytest.fixture
def ethereum_tester(ethereum_tester_session):
    tester = ethereum_tester_session
    snapshot = tester.take_snapshot()
    yield tester
    tester.revert_to_snapshot(snapshot)


@pytest.fixture()
def web3(ethereum_tester):
    web3 = Web3(EthereumTesterProvider(ethereum_tester))
    web3.eth.defaultAccount = web3.eth.accounts[0]
    return web3


@pytest.fixture()
def accounts(web3):
    accounts = web3.personal.listAccounts[0:5]
    assert len(accounts) == 5
    return [to_checksum_address(account) for account in accounts]
