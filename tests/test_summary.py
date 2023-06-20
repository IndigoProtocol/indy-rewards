import datetime

import pandas as pd
import pytest
import pytest_mock

from indy_rewards import summary
from indy_rewards.models import IndividualReward

EPOCH_397_SUMMARY = (
    ("INDY staking reward", 2397.999589),
    ("Reward for providing iBTC liquidity on Minswap", 486.839862),
    ("Reward for providing iBTC liquidity on MuesliSwap", 0.989392),
    ("Reward for providing iBTC liquidity on WingRiders", 856.772141),
    ("Reward for providing iETH liquidity on Minswap", 142.546643),
    ("Reward for providing iETH liquidity on WingRiders", 1233.988660),
    ("Reward for providing iUSD liquidity on Minswap", 40.855223),
    ("Reward for providing iUSD liquidity on MuesliSwap", 15.905051),
    ("Reward for providing iUSD liquidity on WingRiders", 2017.102337),
    ("SP reward for iBTC", 7956.638670),
    ("SP reward for iETH", 7676.927049),
    ("SP reward for iUSD", 13134.431742),
)

EPOCH_397_TOTALS = (
    ("Total INDY staking reward", 2397.999589),
    ("Total LP reward", 4794.999309),
    ("Total SP reward", 28767.997461),
    ("Total", 35960.996359),
)

pd.set_option("display.max_columns", None)


def test_epoch_summary_no_totals():
    epoch_rewards = summary.get_epoch_all_rewards(
        397,
        28768,
        4795,
        2398,
    )
    result = summary.get_summary(
        epoch_rewards,
        False,
    )

    expected = EPOCH_397_SUMMARY

    pd.testing.assert_frame_equal(
        result, pd.DataFrame(expected, columns=["Purpose", "Amount"])
    )

    summary.sp.get_epoch_rewards_per_staker.assert_called_once()
    summary.lp.distribution.get_rewards_per_staker.assert_called()
    summary.gov.get_epoch_rewards_per_staker.assert_called_once()


def test_epoch_summary_with_totals():
    epoch_rewards = summary.get_epoch_all_rewards(
        397,
        28768,
        4795,
        2398,
    )
    result = summary.get_summary(epoch_rewards)

    expected = EPOCH_397_SUMMARY + EPOCH_397_TOTALS

    pd.testing.assert_frame_equal(
        result, pd.DataFrame(expected, columns=["Purpose", "Amount"])
    )

    summary.sp.get_epoch_rewards_per_staker.assert_called_once()
    summary.lp.distribution.get_rewards_per_staker.assert_called()
    summary.gov.get_epoch_rewards_per_staker.assert_called_once()


def test_split_purpose_indy():
    assert summary._split_purpose("INDY staking reward") == (
        "INDY staking reward",
        None,
    )


def test_split_purpose_lp_1():
    assert summary._split_purpose("Reward for providing iBTC liquidity on Minswap") == (
        "LP reward",
        "iBTC on Minswap",
    )


def test_split_purpose_lp_2():
    assert summary._split_purpose(
        "Reward for providing iETH liquidity on WingRiders"
    ) == ("LP reward", "iETH on WingRiders")


def test_split_purpose_sp():
    assert summary._split_purpose("SP reward for iUSD") == ("SP reward", "iUSD")


def get_filtered_rewards(purpose_startswith):
    rewards = pd.read_csv("tests/data/expected-outputs/397-all.csv")
    rewards_filtered_purpose = rewards.loc[
        rewards["Purpose"].str.startswith(purpose_startswith)
    ]
    return rewards_filtered_purpose


def mocked_sp_calc(*args):
    df = get_filtered_rewards("SP reward for ")
    mock_rewards = []
    for _, row in df.iterrows():
        date_str = row["Date"]
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        mock_rewards.append(
            IndividualReward(
                indy=row["Amount"] / 1e6,
                day=date_obj,
                pkh=row["Address"],
                expiration=get_expiration(date_obj),
                description=row["Purpose"],
            )
        )
    return mock_rewards


def mocked_lp_calc(day: datetime.date, epoch_indy: int):
    def make_structured(df):
        rewards = []
        for _, row in df.iterrows():
            day = datetime.date.fromisoformat(row["Date"])
            if "Expiration" in row:
                expiration = row["Expiration"]
            else:
                expiration = get_expiration(day)
            rewards.append(
                IndividualReward(
                    day=day,
                    description=row["Purpose"],
                    expiration=expiration,
                    indy=float(row["Amount"]) / 1_000_000.0,
                    pkh=row["Address"],
                )
            )
        return rewards

    lp_rewards = get_filtered_rewards("Reward for providing ")
    lp_rewards_one_day = lp_rewards.loc[lp_rewards["Date"].eq(day.isoformat())]

    return make_structured(lp_rewards_one_day)


def mocked_gov_distribution(epoch: int, epoch_indy: float):
    df = get_filtered_rewards("INDY staking reward")
    gov_rewards = []
    for row in df.itertuples(index=False):
        day = datetime.datetime.strptime(row.Date, "%Y-%m-%d").date()
        expiration = row["Expiration"] if "Expiration" in row else get_expiration(day)
        gov_rewards.append(
            IndividualReward(
                indy=row.Amount / 1e6,
                day=day,
                pkh=row.Address,
                expiration=expiration,
                description=row.Purpose,
            )
        )
    return gov_rewards


@pytest.fixture(autouse=True)
def mock_summary_dependencies(mocker: pytest_mock.MockerFixture):
    mocker.patch("indy_rewards.sp.get_epoch_rewards_per_staker", wraps=mocked_sp_calc)
    mocker.patch(
        "indy_rewards.summary.lp.distribution.get_rewards_per_staker",
        wraps=mocked_lp_calc,
    )
    mocker.patch(
        "indy_rewards.summary.gov.get_epoch_rewards_per_staker",
        wraps=mocked_gov_distribution,
    )


def get_expiration(
    day: datetime.date, reference_date: datetime.date = datetime.date(2023, 5, 10)
) -> datetime.datetime:
    """Get reward expiration datetime for a given day.

    Calculates the expiration datetime for a given date. The expiration day is the next
    epoch snapshot day after the input day with an additional 90 days. The expiration
    time is set at 21:45.

    The epoch snapshot day is defined as the day that is a multiple of 5 days after a
    fixed reference date.

    Args:
        day (datetime.date): The input date.
        reference_date (datetime.date, optional): The reference date for calculating the
            epoch snapshot day.

    Returns:
        datetime.datetime: The calculated expiration datetime.
    """
    days_since_reference = (day - reference_date).days
    days_to_next_snapshot = (
        5 - (days_since_reference % 5) if days_since_reference % 5 != 0 else 0
    )
    next_snapshot_day = day + datetime.timedelta(days=days_to_next_snapshot)
    expiration_day = next_snapshot_day + datetime.timedelta(days=90)
    expiration_datetime = datetime.datetime.combine(
        expiration_day, datetime.datetime.min.time()
    ) + datetime.timedelta(hours=21, minutes=45)

    return expiration_datetime
