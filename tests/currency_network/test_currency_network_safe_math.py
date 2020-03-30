import pytest
from eth_tester.exceptions import TransactionFailed


MAX_UINT_64 = 2 ** 64 - 1
MAX_INT_72 = 2 ** 71 - 1
MIN_INT_72 = -(2 ** 71)


@pytest.fixture(scope="session")
def safe_math_contract(deploy_contract):
    return deploy_contract("TestCurrencyNetworkSafeMath")


@pytest.mark.parametrize(
    "a, b, c",
    [
        (10, 4, 14),
        (0, MAX_UINT_64, MAX_UINT_64),
        (MAX_UINT_64, 0, MAX_UINT_64),
        ((MAX_UINT_64 - 1) // 2, (MAX_UINT_64 + 1) // 2, MAX_UINT_64),
    ],
)
def test_add_uint_uint_succ(safe_math_contract, a, b, c):
    assert safe_math_contract.functions.testSafeAdd(a, b).call() == c


@pytest.mark.parametrize(
    "a, b", [(1, MAX_UINT_64), (MAX_UINT_64, 1), (MAX_UINT_64, MAX_UINT_64)]
)
def test_add_uint_uint_fail(safe_math_contract, a, b):
    with pytest.raises(TransactionFailed):
        safe_math_contract.functions.testSafeAdd(a, b).call()


@pytest.mark.parametrize(
    "a, b, c",
    [
        (-10, 4, -14),
        (10, 4, 6),
        (0, MAX_UINT_64, -MAX_UINT_64),
        (-MAX_UINT_64, MAX_UINT_64, -2 * MAX_UINT_64),
        (MIN_INT_72, 0, MIN_INT_72),
        (MIN_INT_72 + 1, 1, MIN_INT_72),
    ],
)
def test_sub_uint_int_succ(safe_math_contract, a, b, c):
    assert safe_math_contract.functions.testSafeSubInt(a, b).call() == c


@pytest.mark.parametrize(
    "a, b", [(MIN_INT_72 + 50, 51), (MIN_INT_72, 1), (MIN_INT_72, MAX_UINT_64)]
)
def test_sub_uint_int_fail(safe_math_contract, a, b):
    with pytest.raises(TransactionFailed):
        safe_math_contract.functions.testSafeSubInt(a, b).call()


@pytest.mark.parametrize("a, c", [(0, 0), (5, -5), (MAX_INT_72, -MAX_INT_72)])
def test_minus_int(safe_math_contract, a, c):
    assert safe_math_contract.functions.testSafeMinus(a).call() == c


@pytest.mark.parametrize("a", [MIN_INT_72])
def test_minus_fail(safe_math_contract, a):
    with pytest.raises(TransactionFailed):
        safe_math_contract.functions.testSafeMinus(a).call()
