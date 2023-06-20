import datetime
import statistics
from collections import defaultdict
from typing import Optional

from .. import analytics_api, coingecko_api, config, time_utils
from ..models import IAsset, IAssetReward, StabilityPool
from . import distribution


def get_epoch_aprs(epoch: int, epoch_indy: float) -> dict[StabilityPool, float]:
    daily_aprs: dict[StabilityPool, list[float]] = defaultdict(list)
    indy_prices = coingecko_api.get_indy_ada_daily_closing_prices()

    for day in time_utils.get_epoch_snapshot_dates(epoch):
        daily = get_daily_aprs(day, epoch_indy, indy_prices)
        for sp, apr in daily.items():
            daily_aprs[sp].append(apr)

    epoch_averages = _average_aprs(daily_aprs)
    return epoch_averages


def get_daily_aprs(
    day: datetime.date,
    epoch_indy: float,
    indy_prices: Optional[dict[datetime.date, float]] = None,
) -> dict[StabilityPool, float]:
    if not indy_prices:
        indy_prices = coingecko_api.get_indy_ada_daily_closing_prices()
    iasset_ada_prices = analytics_api.get_iasset_ada_prices(day)
    sp_supplies = analytics_api.get_stability_pool_iasset_supplies(day)

    # We'll assume each iAsset has at least one staker.
    iassets = config.get_active_iassets(day)
    # Nobody is eligible for rewards on the first day.
    iassets = set(filter(lambda x: day != config.IASSET_LAUNCH_DATES[x], iassets))

    sp_rewards = distribution.get_rewards_per_pool(day, epoch_indy, iassets)

    sp_aprs: dict[StabilityPool, float] = {}

    for x in iassets:
        apr = get_apr(day, x, iasset_ada_prices, indy_prices, sp_supplies, sp_rewards)
        sp = StabilityPool(iasset=x)
        sp_aprs[sp] = apr

    return sp_aprs


def get_apr(
    day: datetime.date,
    iasset: IAsset,
    iasset_ada_prices: dict[IAsset, float],
    indy_prices: dict[datetime.date, float],
    sp_supplies: dict[IAsset, float],
    sp_rewards: list[IAssetReward],
) -> float:
    # `a` is the amount of a given iAsset staked in a Stability Pool.
    a: float = sp_supplies[iasset]

    # `b` is a given iAsset price at daily close, denominated in ADA.
    b: float = iasset_ada_prices[iasset]

    # `c` is the daily amount of INDY awarded to a given iAsset's Stability Pool.
    matching_rewards = [r for r in sp_rewards if r.iasset == iasset]
    if len(matching_rewards) != 1:
        raise ValueError(
            f"Expected exactly one IAssetReward for IAsset {iasset.name}, "
            f"got {len(matching_rewards)}"
        )
    c: float = matching_rewards[0].indy

    # `d` is the INDY price at daily close, denominated in ADA.
    d: float = indy_prices[day]

    daily_sp_apr = (c * d) / (a * b) * 365

    return daily_sp_apr


def _average_aprs(
    daily_aprs: dict[StabilityPool, list[float]]
) -> dict[StabilityPool, float]:
    return {sp: statistics.mean(aprs) if aprs else 0 for sp, aprs in daily_aprs.items()}
