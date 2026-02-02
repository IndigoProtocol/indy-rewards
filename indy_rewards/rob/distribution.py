"""Redemption Orderbook (ROB) incentive reward distribution.

Distributes INDY to owners with in-range redemption orderbook positions.
Each epoch is divided into 480 periods of 15 minutes (900 seconds).
For each period, INDY is distributed pro-rata based on each owner's share
of total lovelaceAmount across all in-range positions.
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import analytics_api, time_utils
from ..models import IAsset, IndividualReward


NUM_PERIODS = 480
PERIOD_SECONDS = 900  # 15 minutes
MAX_WORKERS = 20


def get_epoch_rewards_per_staker(
    epoch: int, rob_indy_per_iasset: dict[IAsset, float]
) -> list[IndividualReward]:
    """Get individual ROB INDY rewards for an epoch.

    Fetches all 480 periods once, then distributes INDY per iAsset from
    the same data. This avoids redundant API calls when multiple iAssets
    have non-zero emissions.

    Args:
        epoch: Epoch to calculate rewards for.
        rob_indy_per_iasset: INDY amount to distribute per iAsset for the epoch.
            E.g. {IAsset.iUSD: 500.0, IAsset.iBTC: 0.0, ...}

    Returns:
        List of IndividualReward, one per owner per iAsset (aggregated across
        all 480 periods).
    """
    # Filter to only iAssets with non-zero INDY
    active_iassets = {
        iasset: indy for iasset, indy in rob_indy_per_iasset.items() if indy > 0
    }
    if not active_iassets:
        return []

    epoch_start_date = time_utils.get_epoch_start_date(epoch)
    epoch_start_unix = time_utils.get_snapshot_unix_time(epoch_start_date)
    epoch_end_date = time_utils.get_epoch_end_date(epoch)

    # Fetch all 480 periods once
    all_period_orders = _fetch_all_periods(epoch_start_unix)

    rewards: list[IndividualReward] = []

    for iasset, epoch_indy in active_iassets.items():
        owner_totals = _distribute_for_asset(
            all_period_orders, epoch_indy, iasset.name
        )

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


def _fetch_orders(timestamp: float) -> list[dict]:
    """Fetch redemption orders for a single timestamp."""
    return analytics_api.raw.redemption_orders(timestamp, in_range=True)


def _fetch_all_periods(epoch_start_unix: float) -> list[list[dict]]:
    """Fetch redemption orders for all 480 periods in parallel.

    Returns:
        List of 480 order lists (one per period).
    """
    timestamps = [
        epoch_start_unix + (i * PERIOD_SECONDS) for i in range(NUM_PERIODS)
    ]

    # Use dict to preserve period ordering by timestamp
    results: dict[float, list[dict]] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ts = {
            executor.submit(_fetch_orders, ts): ts for ts in timestamps
        }
        for future in as_completed(future_to_ts):
            ts = future_to_ts[future]
            results[ts] = future.result()

    return [results[ts] for ts in timestamps]


def _distribute_for_asset(
    all_period_orders: list[list[dict]], epoch_indy: float, asset_name: str
) -> dict[str, float]:
    """Distribute INDY for a single asset across all periods.

    Args:
        all_period_orders: Pre-fetched orders for all 480 periods.
        epoch_indy: Total INDY to distribute for this iAsset this epoch.
        asset_name: Only include orders matching this asset (e.g. "iUSD").

    Returns:
        Dict mapping owner PKH to total INDY earned across all periods.
    """
    indy_per_period = epoch_indy / NUM_PERIODS
    owner_totals: dict[str, float] = defaultdict(float)

    for orders in all_period_orders:
        if not orders:
            continue

        # Filter by asset and group by owner, summing lovelaceAmount
        owner_amounts: dict[str, int] = defaultdict(int)
        for order in orders:
            if order["asset"] == asset_name:
                owner_amounts[order["owner"]] += order["lovelaceAmount"]

        total_amount = sum(owner_amounts.values())
        if total_amount == 0:
            continue

        # Distribute pro-rata
        for owner, amount in owner_amounts.items():
            owner_totals[owner] += indy_per_period * amount / total_amount

    return dict(owner_totals)
