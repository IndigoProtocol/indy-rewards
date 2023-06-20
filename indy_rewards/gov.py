import datetime

import pandas as pd

from . import analytics_api, time_utils
from .models import IndividualReward


def get_epoch_rewards_per_staker(
    epoch: int, epoch_indy: float
) -> list[IndividualReward]:
    """Get individual governance staking INDY rewards for an epoch."""
    snap_date = time_utils.get_epoch_end_date(epoch)
    snap_timestamp = time_utils.get_snapshot_unix_time(snap_date)
    account_indy = analytics_api.raw.rewards_staking(snap_timestamp)
    df = pd.DataFrame(account_indy)

    total_staked_indy = df["staked_indy"].sum() / 1e6
    df["pkh_indy"] = df.groupby(["owner"])["staked_indy"].transform("sum") / 1e6
    df["pkh_account_count"] = df.groupby(["owner"])["owner"].transform("count")

    if snap_date < datetime.date(2023, 5, 20):
        df = df.drop_duplicates(subset=["owner"])
    else:
        duplicates = df[df.duplicated(subset="owner", keep=False)]
        if not duplicates.empty:
            raise Exception("Duplicate 'owner' rows in API response.")

    df["reward"] = df.apply(
        lambda row: row["pkh_indy"] * epoch_indy / total_staked_indy, axis=1
    )

    rewards = []

    for row in df.itertuples(index=False):
        rewards.append(
            IndividualReward(
                indy=row.reward,
                day=snap_date,
                pkh=row.owner,
                expiration=time_utils.get_reward_expiration(snap_date),
                description="INDY staking reward",
            )
        )

    return rewards
