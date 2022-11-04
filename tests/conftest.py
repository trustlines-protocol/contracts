import pathlib

from deploy_tools.transact import wait_for_successful_function_call
import pytest

import tldeploy.core
import deploy_tools.transact
import eth_tester.exceptions


from tests.utils import (
    find_gas_values_for_call,
    assert_gas_values_for_call,
    read_test_data,
    GasValues,
    write_test_data,
    assert_gas_costs,
)

EXTRA_DATA = b"\x124Vx\x124Vx\x124Vx\x124Vx"
EXPIRATION_TIME = 4_102_444_800  # 01/01/2100


MAX_UINT_64 = 2 ** 64 - 1
MAX_FEE = MAX_UINT_64


NETWORK_SETTINGS = tldeploy.core.NetworkSettings(
    name="TestCoin",
    symbol="T",
    decimals=6,
    fee_divisor=0,
    default_interest_rate=0,
    custom_interests=False,
    prevent_mediator_interests=False,
    expiration_time=EXPIRATION_TIME,
)


def pytest_addoption(parser):
    parser.addoption(
        UPDATE_GAS_VALUES_OPTION,
        help="Update the gas values snapshot",
        action="store_true",
    )


@pytest.fixture(scope="session", autouse=True)
def bind_contracts(contract_assets):
    tldeploy.core.contracts.data = contract_assets


class CurrencyNetworkAdapter:
    def __init__(self, contract, assert_failing_transaction, assert_failing_call):
        self.contract = contract
        self.assert_failing_transaction = assert_failing_transaction
        self.assert_failing_call = assert_failing_call

    @property
    def expiration_time(self):
        return self.contract.functions.expirationTime().call()

    @property
    def name(self):
        return self.contract.functions.name().call()

    @property
    def symbol(self):
        return self.contract.functions.symbol().call()

    @property
    def decimals(self):
        return self.contract.functions.decimals().call()

    @property
    def is_initialized(self):
        return self.contract.functions.isInitialized().call()

    @property
    def is_network_frozen(self):
        return self.contract.functions.isNetworkFrozen().call()

    @property
    def fee_divisor(self):
        return self.contract.functions.capacityImbalanceFeeDivisor().call()

    @property
    def default_interest_rate(self):
        return self.contract.functions.defaultInterestRate().call()

    @property
    def custom_interests(self):
        return self.contract.functions.customInterests().call()

    @property
    def prevent_mediator_interests(self):
        return self.contract.functions.preventMediatorInterests().call()

    @property
    def owner(self):
        return self.contract.functions.owner().call()

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
        should_fail=False,
        transaction_options=None,
    ):
        function_call = self.contract.functions.setAccount(
            a_address,
            b_address,
            creditline_given,
            creditline_received,
            interest_rate_given,
            interest_rate_received,
            is_frozen,
            m_time,
            balance,
        )
        self._transact_with_function_call(
            function_call,
            transaction_options=transaction_options,
            should_fail=should_fail,
        )

    def get_account(self, a_address, b_address):
        return self.contract.functions.getAccount(a_address, b_address).call()

    def check_account(
        self,
        a_address,
        b_address,
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

    def set_trustline_request(
        self,
        creditor,
        debtor,
        creditline_given=None,
        creditline_received=None,
        interest_rate_given=None,
        interest_rate_received=None,
        is_frozen=None,
        transaction_options=None,
        should_fail=False,
    ):
        function_call = self.contract.functions.setTrustlineRequest(
            creditor,
            debtor,
            creditline_given,
            creditline_received,
            interest_rate_given,
            interest_rate_received,
            is_frozen,
        )
        self._transact_with_function_call(
            function_call,
            transaction_options=transaction_options,
            should_fail=should_fail,
        )

    def set_on_boarder(
        self, on_boardee, on_boarder, transaction_options=None, should_fail=False
    ):
        function_call = self.contract.functions.setOnboarder(on_boardee, on_boarder)
        self._transact_with_function_call(
            function_call,
            transaction_options=transaction_options,
            should_fail=should_fail,
        )

    def get_on_boarder(self, user):
        return self.contract.functions.onboarder(user).call()

    def balance(self, a_address, b_address):
        return self.contract.functions.balance(a_address, b_address).call()

    def balance_with_interests(
        self, balance, old_mtime, new_mtime, interest_rate_given, interest_rate_received
    ):
        return self.contract.functions.calculateBalanceWithInterests(
            balance, old_mtime, new_mtime, interest_rate_given, interest_rate_received
        ).call()

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
        transfer=None,
        accept=False,
        should_fail=False,
    ):
        if transfer is not None:
            function_call = self.contract.functions.updateTrustline(
                debtor_address,
                creditline_given,
                creditline_received,
                interest_rate_given,
                interest_rate_received,
                is_frozen,
                transfer,
            )
        else:
            function_call = self.contract.functions.updateTrustline(
                debtor_address,
                creditline_given,
                creditline_received,
                interest_rate_given,
                interest_rate_received,
                is_frozen,
            )
        self._transact_with_function_call(
            function_call, {"from": creditor_address}, should_fail
        )

        if accept:
            if transfer is not None:
                self.contract.functions.updateTrustline(
                    creditor_address,
                    creditline_received,
                    creditline_given,
                    interest_rate_received,
                    interest_rate_given,
                    is_frozen,
                    -transfer,
                ).transact({"from": debtor_address})
            else:
                self.contract.functions.updateTrustline(
                    creditor_address,
                    creditline_received,
                    creditline_given,
                    interest_rate_received,
                    interest_rate_given,
                    is_frozen,
                ).transact({"from": debtor_address})

    def cancel_trustline_update(self, from_address, to_address, should_fail=False):
        function_call = self.contract.functions.cancelTrustlineUpdate(to_address)
        self._transact_with_function_call(
            function_call, {"from": from_address}, should_fail
        )

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

    def close_trustline_by_direct_transfer(
        self,
        from_address,
        to_address,
        min_balance=0,
        max_balance=None,
        transaction_options=None,
        should_fail=False,
    ):
        if max_balance is None:
            max_balance = self.contract.functions.balance(
                from_address, to_address
            ).call()
        if transaction_options is None:
            transaction_options = {}
        if "from" not in transaction_options:
            transaction_options["from"] = from_address

        function_call = self.contract.functions.closeTrustlineByDirectTransfer(
            to_address, min_balance, max_balance
        )
        self._transact_with_function_call(
            function_call,
            transaction_options=transaction_options,
            should_fail=should_fail,
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

    def transfer(
        self,
        value: int,
        *,
        path,
        max_fee=MAX_FEE,
        extra_data=EXTRA_DATA,
        should_fail=False,
    ):
        function_call = self.contract.functions.transfer(
            value, max_fee, path, extra_data
        )
        self._transact_with_function_call(function_call, {"from": path[0]}, should_fail)

    def transfer_receiver_pays(
        self,
        value: int,
        *,
        path,
        max_fee=MAX_FEE,
        extra_data=EXTRA_DATA,
        should_fail=False,
    ):
        function_call = self.contract.functions.transferReceiverPays(
            value, max_fee, path, extra_data
        )
        self._transact_with_function_call(function_call, {"from": path[0]}, should_fail)

    def transfer_from(
        self,
        msg_sender,
        value: int,
        *,
        path,
        max_fee=MAX_FEE,
        extra_data=EXTRA_DATA,
        should_fail=False,
    ):
        function_call = self.contract.functions.transferFrom(
            value, max_fee, path, extra_data
        )
        self._transact_with_function_call(
            function_call, {"from": msg_sender}, should_fail
        )

    def debit_transfer(
        self, value, *, max_fee=MAX_FEE, path, extra_data=EXTRA_DATA, should_fail=False
    ):
        function_call = self.contract.functions.debitTransfer(
            value, max_fee, path, extra_data
        )
        self._transact_with_function_call(
            function_call, {"from": path[len(path) - 1]}, should_fail
        )

    def increase_debt(self, debtor, creditor, value):
        return self.contract.functions.increaseDebt(creditor, value).transact(
            {"from": debtor}
        )

    def set_debt(
        self, debtor, creditor, value, transaction_options=None, should_fail=False
    ):
        function_call = self.contract.functions.setDebt(debtor, creditor, value)
        self._transact_with_function_call(
            function_call,
            transaction_options=transaction_options,
            should_fail=should_fail,
        )

    def get_debt(self, debtor, creditor):
        return self.contract.functions.getDebt(debtor, creditor).call()

    def get_all_debtors(self):
        return self.contract.functions.getAllDebtors().call()

    def get_debtors_of_user(self, user):
        return self.contract.functions.getDebtorsOfUser(user).call()

    def add_authorized_address(self, *, target, sender):
        self.contract.functions.addAuthorizedAddress(target).transact({"from": sender})

    def remove_authorized_address(self, *, target, sender, should_fail=False):
        function_call = self.contract.functions.removeAuthorizedAddress(target)
        self._transact_with_function_call(function_call, {"from": sender}, should_fail)

    def remove_owner(self, sender, should_fail=False):
        function_call = self.contract.functions.removeOwner()
        self._transact_with_function_call(
            function_call, transaction_options={"from": sender}, should_fail=should_fail
        )

    def freeze_network(self, should_fail=False):
        function_call = self.contract.functions.freezeNetwork()
        self._transact_with_function_call(function_call, should_fail=should_fail)

    def freeze_network_if_not_frozen(self, should_fail=False):
        if self.contract.functions.isNetworkFrozen().call():
            return
        function_call = self.contract.functions.freezeNetwork()
        self._transact_with_function_call(function_call, should_fail=should_fail)

    def unfreeze_network(self, transaction_options=None, should_fail=False):
        function_call = self.contract.functions.unfreezeNetwork()
        self._transact_with_function_call(
            function_call,
            transaction_options=transaction_options,
            should_fail=should_fail,
        )

    def is_trustline_frozen(self, a, b):
        return self.contract.functions.isTrustlineFrozen(a, b).call()

    def get_friends(self, a):
        return self.contract.functions.getFriends(a).call()

    def get_users(self):
        return self.contract.functions.getUsers().call()

    def events(self, event_name: str, from_block: int = 0):
        return list(
            getattr(self.contract.events, event_name).getLogs(fromBlock=from_block)
        )

    def _transact_with_function_call(
        self, function_call, transaction_options=None, should_fail=False
    ):
        if should_fail:
            self.assert_failing_transaction(function_call, transaction_options)
        else:
            function_call.transact(transaction_options)


UPDATE_GAS_VALUES_OPTION = "--update-gas-values"


@pytest.fixture(scope="session")
def gas_values_snapshot(pytestconfig):
    """Returns a GasValueSnapshoter, an object to assert gas values based on created snapshots"""
    snapshot_filename = "gas_values.csv"

    class GasValueSnapshoter:
        UNKNOWN = -1

        def __init__(self, data, *, update=False):
            """
            Creates gas values snapshots and let assert that the values did not change
            Snapshot data is updated when it does not exist, or when  `update` is set. In this case
            tests always succeed.
            :param data: The snapshot data
            :param update: True, if existing values should be updated or not
            """
            self.update = update
            self.data = data

        def assert_gas_values_match_for_call(
            self, key, web3, contract_call, transaction_options=None
        ):
            """
            Assert that the gas values of a contract call are correct and did not change.
            This will execute the contract call once.
            """
            if key not in self.data or self.update:
                gas_values = find_gas_values_for_call(
                    web3, contract_call, transaction_options=transaction_options
                )
                self.data[key] = gas_values
            else:
                assert_gas_values_for_call(
                    web3,
                    contract_call,
                    transaction_options=transaction_options,
                    gas_cost_estimation=self.data[key].cost,
                    gas_limit=self.data[key].limit,
                )

        def assert_gas_costs_match(self, key, gas_cost, *, abs_delta=100):
            """Assert that the gas cost did not change within the allowed delta.
            This will not execute any transaction and can thus not check
            the gas limit."""
            if key not in self.data or self.update:
                self.data[key] = GasValues(gas_cost, self.UNKNOWN)
            else:
                assert_gas_costs(gas_cost, self.data[key].cost, abs_delta=abs_delta)

    snapshot_path = pathlib.Path(__file__).parent.absolute() / snapshot_filename
    snapshoter = GasValueSnapshoter(
        data=read_test_data(snapshot_path, data_class=GasValues),
        update=pytestconfig.getoption(UPDATE_GAS_VALUES_OPTION, default=False),
    )

    yield snapshoter

    write_test_data(snapshot_path, ["KEY", "GAS_COST", "GAS_LIMIT"], snapshoter.data)


def get_events_of_contract(contract, event_name, from_block=0):
    return list(getattr(contract.events, event_name).getLogs(fromBlock=from_block))


def get_single_event_of_contract(contract, event_name, from_block=0):
    events = get_events_of_contract(contract, event_name, from_block)
    assert len(events) == 1, f"No single event of type {event_name}"
    return events[0]


@pytest.fixture(scope="session")
def assert_failing_transaction(web3):
    def asserting_function(function_transact, transaction_options=None):
        """Assert that a transaction will fail.
        `function_transact` is prepared from a web3 contract via contract.functions.functionName(args)"""

        if transaction_options is None:
            transaction_options = {}
        if "gas" not in transaction_options.keys():
            # We use a gas limit to prevent eth_tester from failing prematurely
            transaction_options["gas"] = 2_000_000

        with pytest.raises(deploy_tools.transact.TransactionFailed):
            wait_for_successful_function_call(
                function_transact, web3=web3, transaction_options=transaction_options
            )

    return asserting_function


@pytest.fixture(scope="session")
def assert_failing_call(
    web3,
):
    def asserting_function(function_call, transaction_options=None):
        """Assert that a call will fail.
        `function_call` is prepared from a web3 contract via contract.functions.functionName(args)"""

        if transaction_options is None:
            transaction_options = {}
        if "gas" not in transaction_options.keys():
            # We use a gas limit even though it makes no sense for a call
            # to prevent eth_tester from failing prematurely
            transaction_options["gas"] = 2_000_000

        with pytest.raises(eth_tester.exceptions.TransactionFailed):
            function_call.call(transaction_options)

    return asserting_function


@pytest.fixture(scope="session")
def make_currency_network_adapter(assert_failing_transaction, assert_failing_call):
    def make(contract):
        return CurrencyNetworkAdapter(
            contract,
            assert_failing_transaction=assert_failing_transaction,
            assert_failing_call=assert_failing_call,
        )

    return make
