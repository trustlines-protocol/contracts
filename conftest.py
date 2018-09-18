import os
import pytest
import subprocess
import shutil
import io

from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def compile_contracts():
    """compile the contracts with populus before running the tests"""
    cwd = os.getcwd()
    try:
        here = Path(__file__).parent
        os.chdir(here)
        err = os.system("make")
        assert err == 0, "make failed"
        os.environ["TRUSTLINES_CONTRACTS_JSON"] = str(here / "build" / "contracts.json")
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
