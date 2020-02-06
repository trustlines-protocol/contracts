import pytest
import eth_tester.backends.pyevm.main
from texttable import Texttable

import tldeploy.core

# increase eth_tester's GAS_LIMIT
# Otherwise we can't deploy our contract
assert eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT < 8 * 10 ** 6
eth_tester.backends.pyevm.main.GENESIS_GAS_LIMIT = 8 * 10 ** 6


EXTRA_DATA = b"\x124Vx\x124Vx\x124Vx\x124Vx"
EXPIRATION_TIME = 4_102_444_800  # 01/01/2100


MAX_UINT_64 = 2 ** 64 - 1
MAX_FEE = MAX_UINT_64


@pytest.fixture(scope="session", autouse=True)
def bind_contracts(contract_assets):
    tldeploy.core.contracts.data = contract_assets


class CurrencyNetworkAdapter:
    def __init__(self, contract):
        self.contract = contract

    def set_account(
        self,
        a_address,
        b_address,
        *,
        creditline_given=0,
        creditline_received=0,
        interest_rate_given=0,
        interest_rate_received=0,
        is_frozen=False,
        m_time=0,
        balance=0,
    ):
        self.contract.functions.setAccount(
            a_address,
            b_address,
            creditline_given,
            creditline_received,
            interest_rate_given,
            interest_rate_received,
            is_frozen,
            m_time,
            balance,
        ).transact()

    def check_account(
        self,
        a_address,
        b_address,
        *,
        creditline_given=None,
        creditline_received=None,
        interest_rate_given=None,
        interest_rate_received=None,
        is_frozen=None,
        m_time=None,
        balance=None,
    ):
        account_tuple = self.contract.functions.getAccount(a_address, b_address).call()

        result = True
        for index, value in enumerate(
            [
                creditline_given,
                creditline_received,
                interest_rate_given,
                interest_rate_received,
                is_frozen,
                m_time,
                balance,
            ]
        ):
            if value is not None and value != account_tuple[index]:
                print(
                    f"Check failed: #{index}: {account_tuple[index]} instead of {value}"
                )
                result = False
        return result

    def balance(self, a_address, b_address):
        return self.contract.functions.balance(a_address, b_address).call()

    def creditline(self, creditor_address, debtor_address):
        return self.contract.functions.creditline(
            creditor_address, debtor_address
        ).call()

    def interest_rate(self, creditor_address, debtor_address):
        return self.contract.functions.interestRate(
            creditor_address, debtor_address
        ).call()

    def update_trustline(
        self,
        creditor_address,
        debtor_address,
        *,
        creditline_given=0,
        creditline_received=0,
        interest_rate_given=0,
        interest_rate_received=0,
        is_frozen=False,
        accept=False,
    ):
        self.contract.functions.updateTrustline(
            debtor_address,
            creditline_given,
            creditline_received,
            interest_rate_given,
            interest_rate_received,
            is_frozen,
        ).transact({"from": creditor_address})

        if accept:
            self.contract.functions.updateTrustline(
                creditor_address,
                creditline_received,
                creditline_given,
                interest_rate_received,
                interest_rate_given,
                is_frozen,
            ).transact({"from": debtor_address})

    def close_trustline(
        self, user_address, other_address, *, path=None, max_fee=MAX_FEE
    ):
        if path:
            self.contract.functions.closeTrustlineByTriangularTransfer(
                other_address, max_fee, path
            ).transact({"from": user_address})
        self.contract.functions.closeTrustline(other_address).transact(
            {"from": user_address}
        )

    def is_trustline_closed(self, a_address, b_address):
        return (
            self.check_account(
                a_address,
                b_address,
                creditline_given=0,
                creditline_received=0,
                interest_rate_given=0,
                interest_rate_received=0,
                balance=0,
            )
            and a_address not in self.contract.functions.getFriends(b_address).call()
            and b_address not in self.contract.functions.getFriends(a_address).call()
        )

    def transfer(self, value: int, *, path, max_fee=MAX_FEE, extra_data=EXTRA_DATA):
        self.contract.functions.transfer(value, max_fee, path, extra_data).transact(
            {"from": path[0]}
        )

    def transfer_from(
        self, msg_sender, value: int, *, path, max_fee=MAX_FEE, extra_data=EXTRA_DATA
    ):
        self.contract.functions.transferFrom(value, max_fee, path, extra_data).transact(
            {"from": msg_sender}
        )

    def add_authorized_address(self, *, target, sender):
        self.contract.functions.addAuthorizedAddress(target).transact({"from": sender})

    def remove_authorized_address(self, *, target, sender):
        self.contract.functions.removeAuthorizedAddress(target).transact(
            {"from": sender}
        )

    def events(self, event_name: str):
        return list(getattr(self.contract.events, event_name).getLogs(fromBlock=0))


@pytest.fixture(scope="session")
def table():
    table = Texttable()
    table.add_row(["Topic", "Gas cost"])
    yield table
    print()
    print(table.draw())


def get_gas_costs(web3, tx_hash):
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    return tx_receipt.gasUsed


def report_gas_costs(table: Texttable, topic: str, gas_cost: int, limit: int) -> None:
    table.add_row([topic, gas_cost])
    assert (
        gas_cost <= limit
    ), "Cost for {} were {} gas and exceeded the limit {}".format(
        topic, gas_cost, limit
    )
