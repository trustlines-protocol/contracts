import os
import subprocess
import shutil
import io
from pathlib import Path

import pytest
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider
from eth_utils import to_checksum_address, encode_hex
import eth_tester
import eth_tester.backends.pyevm.main


@pytest.fixture(scope="session", autouse=True)
def compile_contracts():
    """compile the contracts before running the tests"""
    cwd = os.getcwd()
    try:
        root = Path(__file__).parent.parent
        os.chdir(root)
        err = os.system("deploy-tools compile -o")
        assert err == 0, "Compilation failed"
        os.environ["TRUSTLINES_CONTRACTS_JSON"] = str(root / "build" / "contracts.json")
    finally:
        os.chdir(cwd)


def _find_solc(msgs):
    solc = shutil.which("solc")
    if solc:
        msgs.write("solc: {}\n".format(solc))
    else:
        msgs.write("solc: <NOT FOUND>\n")
    return solc


def _get_solc_version(msgs):
    try:
        process = subprocess.Popen(['solc', '--version'], stdout=subprocess.PIPE)
    except Exception as err:
        msgs.write("solidity version: <ERROR {}>".format(err))
        return

    out, err = process.communicate()

    lines = out.decode('utf-8').splitlines()
    for line in lines:
        if line.startswith("Version: "):
            msgs.write("solidity version: {}\n".format(line[len("Version: "):]))
            break
    else:
        msgs.write("solidity version: <UNKNOWN>")


def pytest_report_header(config):
    msgs = io.StringIO()
    solc = _find_solc(msgs)

    if solc:
        _get_solc_version(msgs)

    return msgs.getvalue()


@pytest.fixture(scope="session", autouse=True)
def increase_gas_limit():
    """increase eth_tester's GAS_LIMIT

    Otherwise we can't deploy our contract"""
    assert eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT < 6 * 10 ** 6
    eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT = 6 * 10 ** 6


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
