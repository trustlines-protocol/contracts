import pytest
import eth_tester.backends.pyevm.main

import tldeploy.core

# increase eth_tester's GAS_LIMIT
# Otherwise we can't deploy our contract
assert eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT < 8 * 10 ** 6
eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT = 8 * 10 ** 6


EXTRA_DATA = b"\x124Vx\x124Vx\x124Vx\x124Vx"
EXPIRATION_TIME = 4102444800  # 01/01/2100


@pytest.fixture(scope="session", autouse=True)
def bind_contracts(contract_assets):
    tldeploy.core.contracts.data = contract_assets
