import datetime
import statistics
from collections import defaultdict
from typing import Optional

from .. import analytics_api, coingecko_api, time_utils
from ..models import IAsset, LiquidityPool, LiquidityPoolReward, LiquidityPoolStatus
from . import distribution


def get_epoch_aprs(
    epoch: int, epoch_indy: float, only_day: Optional[datetime.date] = None
) -> dict[LiquidityPool, float]:
    indy_prices = coingecko_api.get_indy_ada_daily_closing_prices()
    daily_aprs: dict[LiquidityPool, list[float]] = defaultdict(list)
    days = time_utils.get_epoch_snapshot_dates(epoch)

    for day in days:
        if only_day and day != only_day:
            continue

        iasset_ada_prices = analytics_api.get_iasset_ada_prices(day)
        lp_statuses = analytics_api.get_lp_status(day, with_lp_token_supplies=True)
        iasset_group_rewards = distribution.get_iassets_daily_indy(day, epoch_indy)
        lp_rewards = distribution.distribute_to_liquidity_pools(
            iasset_group_rewards, lp_statuses, day
        )

        for lp_status in lp_statuses:
            pool_rewards = tuple(filter(lambda x: x.lp == lp_status.lp, lp_rewards))
            if len(pool_rewards) != 1:
                raise Exception(
                    f"Expected to find exactly 1 LP reward entry for day "
                    f"{day} + {lp_status.lp.dex.name} + {lp_status.lp.iasset.name}, "
                    f"but got {len(pool_rewards)}"
                )
            single_lp_reward = pool_rewards[0]
            daily_aprs[lp_status.lp].append(
                get_lp_daily_apr(
                    day, lp_status, iasset_ada_prices, single_lp_reward, indy_prices
                )
            )

    return _average_aprs(daily_aprs)


def get_lp_daily_apr(
    day: datetime.date,
    stat: LiquidityPoolStatus,
    iasset_ada_prices: dict[IAsset, float],
    lp_indy_reward: LiquidityPoolReward,
    indy_prices: dict[datetime.date, float],
) -> float:
    """Calculates the INDY-based LP APR for a given day and LP.

    Loosely based on this LP token staking formula, but returns APRs per liquidity pool
    (more granular) APRs, rather than per iAsset (liquidity pools for the same iAsset
    lumped together and averaged):
    https://docs.indigoprotocol.io/resources/protocol-statistics/apr-apy-calculations

    Different liquidity pools of the same iAsset can have different APRs, depending on
    how many of their total LP tokens are deposited (staked) to Indigo for each LP,
    relative to the LP's total token supply.
    """

    # `a` is the liquidity pool's iAsset amount for which the LP tokens are locked
    # (staked) into Indigo.
    if stat.lp_token_staked is not None and stat.lp_token_circ_supply is not None:
        a: float = stat.iasset_balance * (
            stat.lp_token_staked / stat.lp_token_circ_supply
        )
    else:
        raise Exception("LP token supply information not set")

    # `b` is the iAsset price at daily close, denominated in ADA.
    # "How much ADA is 1 iAsset worth?"
    # e.g. for iBTC: 75615.354605, for iUSD: 2.777777
    b: float = iasset_ada_prices[stat.lp.iasset]

    # `c` is the daily amount of INDY awarded to stakers of the LP.
    c: float = lp_indy_reward.indy

    # `d` is the INDY price at daily close, denominated in ADA.
    d: float = indy_prices[day]

    daily_lp_apr = (c * d) / (2 * a * b) * 365

    return daily_lp_apr


def _average_aprs(
    daily_aprs: dict[LiquidityPool, list[float]]
) -> dict[LiquidityPool, float]:
    return {lp: statistics.mean(aprs) if aprs else 0 for lp, aprs in daily_aprs.items()}
