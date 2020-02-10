import pytest

# run this with 'pytest -k audit -s'. This test doesn't fail at the
# moment.


def as_seconds(years):
    """compute duration in years to seconds"""
    return int(years * 365 * 3600 * 24)


@pytest.fixture(scope="session")
def test_currency_network_contract(deploy_contract):
    return deploy_contract("TestCurrencyNetwork")


def test_negative_interests(test_currency_network_contract):
    """test interests with negative balances"""
    for rate in [-1000, -2000, -3000, -4000, -5000, -10000, -15000, -32768]:
        for duration in [1, 2, 3, 4, 5]:
            factors = []
            print(f"===> rate:{rate:5d} duration: {duration}")
            for balance in (1000, 10 ** 6, 10 ** 18, 10 ** 19, 10 ** 20, 10 ** 21):
                new_balance = test_currency_network_contract.functions.testCalculateBalanceWithInterests(
                    balance, 0, as_seconds(duration), rate, rate
                ).call()
                # The new balance should not turn negative suddenly
                # and it should decrease given that we only have
                # negative interests here.
                ok = 0 <= new_balance <= balance
                print(
                    f"{'+' if ok else '-'} balance:{balance:25d} new_balance:{new_balance:25d} {new_balance / balance}"
                )
                factors.append(new_balance / balance)
            # we should end up with around the same percentage of the original balance for each of those
            if min(factors) < 0.95 * max(factors):
                print("Error: factors vary too much")
            print()
