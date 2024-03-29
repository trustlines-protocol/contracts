from typing import NamedTuple
import csv

from eth_utils.exceptions import ValidationError


class GasValues(NamedTuple):
    cost: int
    limit: int


class GasCalculationError(Exception):
    pass


def assert_gas_costs(actual, expected, *, abs_delta=0):
    """Asserts the gas costs within the allowed delta"""
    assert (
        not actual < expected - abs_delta
    ), "The gas costs decreased from {} to {}".format(expected, actual)
    assert (
        not actual > expected + abs_delta
    ), "The gas costs increased from {} to {}".format(expected, actual)


def assert_gas_values_for_call(
    web3,
    contract_call,
    *,
    gas_cost_estimation,
    gas_limit=None,
    transaction_options=None,
    abs_gas_delta=1000,
):
    """Executes the contract call and asserts the gas values

    It checks that the gas usage matches the `gas_cost_estimation` and it checks
    that the gas limit is within [`gas_limit` - `abs_gas_delta`, `gas_limit`].
    It does so by first trying the contract call with a gas limit reduced by `abs_gas_delta`
    and asserts that it fails, and then checks that the call
    with `gas_limits` succeeds. If `gas_limit` is not given, `gas_cost_estimation` will be used as gas
    limit.
    """
    if transaction_options is None:
        transaction_options = {}

    if gas_limit is None:
        gas_limit = gas_cost_estimation

    transaction_options.update({"gas": gas_limit - abs_gas_delta})
    assert_contract_call_fails(
        web3,
        contract_call,
        transaction_options=transaction_options,
        message="The transaction did not fail with reduced gas, gas limit to high?",
    )

    transaction_options.update({"gas": gas_limit})

    tx_hash = assert_contract_call_succeeds(
        web3,
        contract_call,
        transaction_options=transaction_options,
        message="Transaction failed, gas limit to low?",
    )

    gas_cost = get_gas_costs(web3, tx_hash)

    assert_gas_costs(gas_cost, gas_cost_estimation)


def assert_contract_call_status(
    web3, contract_call, status, *, transaction_options, message
):

    tx_hash = None
    try:
        tx_hash = contract_call.transact(transaction_options)
        tx_success = web3.eth.wait_for_transaction_receipt(tx_hash, 5).status == 1
    except ValidationError as e:
        if "Insufficient gas" not in e.args:
            raise e
        else:
            tx_success = False
    assert tx_success == status, message
    return tx_hash


def assert_contract_call_succeeds(
    web3, contract_call, *, transaction_options, message=None
):
    if message is None:
        message = "Transaction failed"
    return assert_contract_call_status(
        web3,
        contract_call,
        status=True,
        transaction_options=transaction_options,
        message=message,
    )


def assert_contract_call_fails(
    web3, contract_call, *, transaction_options, message=None
):
    if message is None:
        message = "Transaction did not fail."
    return assert_contract_call_status(
        web3,
        contract_call,
        status=False,
        transaction_options=transaction_options,
        message=message,
    )


def get_gas_costs(web3, tx_hash):
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    return tx_receipt.gasUsed


def find_gas_values_for_call(web3, contract_call, transaction_options=None):
    if transaction_options is None:
        transaction_options = {}

    gas_limit = 20_000
    tx_success = False

    while not tx_success:
        if gas_limit >= 2_000_000:
            raise GasCalculationError("Gas calculation reached 2_000_000 limit.")
        gas_limit += 1_000
        transaction_options["gas"] = gas_limit
        try:
            tx_hash = contract_call.transact(transaction_options)
            tx_success = web3.eth.wait_for_transaction_receipt(tx_hash, 5).status == 1
        except ValidationError as e:
            if "Insufficient gas" not in e.args:
                raise e
            tx_success = False

    gas_cost = get_gas_costs(web3, tx_hash)
    return GasValues(limit=gas_limit, cost=gas_cost)


def read_test_data(path, *, data_class=tuple, value_class=int):
    if not path.exists():
        path.touch()
    data = {}
    with open(path) as file:
        reader = csv.reader(file, delimiter=" ", lineterminator="\n")
        for i, row in enumerate(reader):
            if i == 0:
                # skip header
                continue
            data[row[0]] = data_class(*[value_class(x) for x in row[1:]])
    return data


def write_test_data(path, header, data):
    with open(path, "w") as file:
        writer = csv.writer(file, delimiter=" ", lineterminator="\n")
        writer.writerow(header)
        for key, value in data.items():
            row = [key]
            row.extend(value)
            assert len(row) == len(header)
            writer.writerow(row)
