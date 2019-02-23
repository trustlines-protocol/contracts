import pytest
import eth_tester.backends.pyevm.main

import tldeploy.core

# increase eth_tester's GAS_LIMIT
# Otherwise we can't deploy our contract
assert eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT < 6 * 10 ** 6
eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT = 6 * 10 ** 6


@pytest.fixture(scope="session", autouse=True)
def bind_contracts(contract_assets):
    tldeploy.core.contracts.data = contract_assets
