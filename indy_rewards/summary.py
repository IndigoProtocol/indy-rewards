import datetime

import pandas as pd

from . import gov, lp, sp, time_utils
from .models import IndividualReward


def get_epoch_all_rewards(
    epoch: int,
    sp_indy: float,
    lp_indy: float,
    gov_indy: float,
) -> list[IndividualReward]:
    """Returns list of SP, LP and gov INDY rewards for accounts for an epoch.

    Args:
        epoch: Epoch to calculate rewards for.
        sp_indy: INDY amount to distribute to SP stakers. E.g. 28768.
        lp_indy: INDY to distribute to LP stakers.
        gov_indy: INDY to distribute to INDY governance stakers.

    Returns:
        Pandas DataFrame with columns:

        - Period: Arbitrary incrementing counter identifying the Sundae import.
        - Address: Account PaymentKeyHash as a hex string.
        - Purpose: Human-readable description, e.g. "SP reward for iUSD".
        - Date: Snapshot date, e.g. 2023-03-17.
        - Amount: INDY in lovelaces, e.g. 1000000 means 1 INDY.
        - Expiration: Date and time after which this reward is no longer claimable,
            e.g. 2023-06-20 21:45.
    """
    gov_rewards = gov.get_epoch_rewards_per_staker(epoch, gov_indy)
    sp_rewards = sp.get_epoch_rewards_per_staker(epoch, sp_indy)

    all_rewards = sp_rewards + gov_rewards

    if epoch < 422:
        all_rewards += lp.get_epoch_rewards_per_staker(epoch, lp_indy)

    return all_rewards


def get_day_all_rewards(
    day: datetime.date,
    sp_indy_per_epoch: float,
    lp_indy_per_epoch: float,
    gov_indy_per_epoch: float,
) -> list[IndividualReward]:
    rewards = []

    epoch = time_utils.date_to_epoch(day)
    epoch_end_date = time_utils.get_epoch_end_date(epoch)
    if epoch_end_date == day:
        rewards += gov.get_epoch_rewards_per_staker(epoch, gov_indy_per_epoch)

    rewards += sp.get_rewards_per_staker(day, sp_indy_per_epoch)
    if day <= datetime.date(2023, 7, 4):
        rewards += lp.get_rewards_per_staker(day, lp_indy_per_epoch)

    return rewards


def get_summary(
    rewards: list[IndividualReward], with_totals: bool = True
) -> pd.DataFrame:
    """Returns a breakdown of INDY rewards.

    Returns:
        Pandas dataframe with two columns:

        - Purpose (e.g. "SP reward for iUSD")
        - Amount (e.g. 2,634.86)
    """
    df = pd.DataFrame(map(lambda x: x.as_dict(), rewards))

    if df.empty:
        return df

    summary = df.groupby(by="Purpose", as_index=False)[["Purpose", "Amount"]].sum(
        numeric_only=True
    )

    summary.Amount /= 1e6

    if with_totals:
        summary = _add_totals(summary)

    return summary


def _add_totals(summary: pd.DataFrame) -> pd.DataFrame:
    def split_row(row):
        purpose_split = _split_purpose(row["Purpose"])
        return (*purpose_split, row["Amount"])

    atomic_summary = summary.apply(split_row, axis=1, result_type="expand")
    atomic_summary.columns = ("purpose_main", "purpose_details", "Amount")

    group_totals = (
        atomic_summary[["purpose_main", "Amount"]]
        .groupby(by="purpose_main", as_index=False)
        .sum()
    )

    group_totals["purpose_main"] = group_totals["purpose_main"].apply(
        lambda x: "Total " + x
    )

    full_total = summary["Amount"].sum()

    return pd.concat(
        (
            summary,
            group_totals.rename(columns={"purpose_main": "Purpose"}),
            pd.DataFrame({"Purpose": "Total", "Amount": full_total}, index=[0]),
        ),
        ignore_index=True,
    )


def _split_purpose(purpose: str) -> tuple[str, ...] | tuple[str, None]:
    """Splits reward description string into main and sub parts."""
    if purpose.startswith("Reward for providing "):
        split = purpose.split()
        return ("LP reward", split[3] + " on " + split[-1])
    elif purpose.startswith("SP reward for "):
        return ("SP reward", purpose.removeprefix("SP reward for "))
    else:
        return (purpose, None)
