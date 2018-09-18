import os
import pytest
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def compile_contracts():
    """compile the contracts with populus"""
    cwd = os.getcwd()
    try:
        here = Path(__file__).parent
        os.chdir(here)
        err = os.system("make")
        assert err == 0, "make failed"
        os.environ["TRUSTLINES_CONTRACTS_JSON"] = str(here / "build" / "contracts.json")
    finally:
        os.chdir(cwd)
