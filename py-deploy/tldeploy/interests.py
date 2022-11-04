# This file provides functions to calculate the interests on a trustline off-chain

SECONDS_PER_YEAR = 60 * 60 * 24 * 365
INTERESTS_DECIMALS = 2
DELTA_TIME_MINIMAL_ALLOWED_VALUE = -60


def _ensure_non_negative_delta_time(delta_time):
    """make sure the delta_time - used for computation of interests - is mostly
    positive. Every value passed in that's less than
    DELTA_TIME_MINIMAL_ALLOWED_VALUE will trigger a ValueError.

    see https://github.com/trustlines-protocol/relay/issues/279
    """
    if delta_time < DELTA_TIME_MINIMAL_ALLOWED_VALUE:
        raise ValueError("delta_time out of bounds")
    return max(delta_time, 0)


def calculate_interests(
    balance: int,
    internal_interest_rate: int,
    delta_time_in_seconds: int,
    highest_order: int = 15,
) -> int:
    delta_time_in_seconds = _ensure_non_negative_delta_time(delta_time_in_seconds)
    intermediate_order = balance
    interests = 0
    # Calculate compound interests using taylor approximation
    for order in range(1, highest_order + 1):
        intermediate_order = int(
            intermediate_order
            * internal_interest_rate
            * delta_time_in_seconds
            / (SECONDS_PER_YEAR * 100 * 10 ** INTERESTS_DECIMALS * order)
        )

        if intermediate_order == 0:
            break
        interests += intermediate_order

    return interests


def balance_with_interests(
    balance: int,
    internal_interest_rate_positive_balance: int,
    internal_interest_rate_negative_balance: int,
    delta_time_in_seconds: int,
) -> int:
    delta_time_in_seconds = _ensure_non_negative_delta_time(delta_time_in_seconds)
    if balance > 0:
        interest = calculate_interests(
            balance, internal_interest_rate_positive_balance, delta_time_in_seconds
        )
    else:
        interest = calculate_interests(
            balance, internal_interest_rate_negative_balance, delta_time_in_seconds
        )
    total = balance + interest
    assert isinstance(total, int)
    return total
