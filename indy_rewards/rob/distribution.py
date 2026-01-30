"""Redemption Orderbook (ROB) incentive reward distribution.

Distributes INDY to owners with in-range redemption orderbook positions.
Each epoch is divided into 480 periods of 15 minutes (900 seconds).
For each period, INDY is distributed pro-rata based on each owner's share
of total lovelaceAmount across all in-range positions.
"""

from collections import defaultdict

from .. import analytics_api, time_utils
from ..models import IAsset, IndividualReward


NUM_PERIODS = 480
PERIOD_SECONDS = 900  # 15 minutes


def get_epoch_rewards_per_staker(
    epoch: int, rob_indy_per_iasset: dict[IAsset, float]
) -> list[IndividualReward]:
    """Get individual ROB INDY rewards for an epoch.

    Args:
        epoch: Epoch to calculate rewards for.
        rob_indy_per_iasset: INDY amount to distribute per iAsset for the epoch.
            E.g. {IAsset.iUSD: 500.0, IAsset.iBTC: 0.0, ...}

    Returns:
        List of IndividualReward, one per owner per iAsset (aggregated across
        all 480 periods).
    """
    epoch_start_date = time_utils.get_epoch_start_date(epoch)
    epoch_start_unix = time_utils.get_snapshot_unix_time(epoch_start_date)
    epoch_end_date = time_utils.get_epoch_end_date(epoch)

    rewards: list[IndividualReward] = []

    for iasset, epoch_indy in rob_indy_per_iasset.items():
        if epoch_indy <= 0:
            continue

        owner_totals = _distribute_across_periods(epoch_start_unix, epoch_indy)

        for owner, total_indy in owner_totals.items():
            rewards.append(
                IndividualReward(
                    indy=total_indy,
                    day=epoch_end_date,
                    pkh=owner,
                    expiration=time_utils.get_reward_expiration(epoch_end_date),
                    description=f"ROB reward for {iasset.name}",
                )
            )

    return rewards


def _distribute_across_periods(
    epoch_start_unix: float, epoch_indy: float
) -> dict[str, float]:
    """Distribute INDY across 480 periods and aggregate by owner.

    Args:
        epoch_start_unix: Unix timestamp of epoch start (21:45 UTC).
        epoch_indy: Total INDY to distribute for this iAsset this epoch.

    Returns:
        Dict mapping owner PKH to total INDY earned across all periods.
    """
    indy_per_period = epoch_indy / NUM_PERIODS
    owner_totals: dict[str, float] = defaultdict(float)

    for i in range(NUM_PERIODS):
        timestamp = epoch_start_unix + (i * PERIOD_SECONDS)
        orders = analytics_api.raw.redemption_orders(timestamp, in_range=True)

        # No in-range orders for a period
        if not orders:
            continue

        # Group by owner and sum lovelaceAmount - Multiple positions per owner
        owner_amounts: dict[str, int] = defaultdict(int)
        for order in orders:
            owner_amounts[order["owner"]] += order["lovelaceAmount"]

        total_amount = sum(owner_amounts.values())
        if total_amount == 0:
            continue

        # Distribute pro-rata
        for owner, amount in owner_amounts.items():
            owner_totals[owner] += indy_per_period * amount / total_amount

    return dict(owner_totals)
