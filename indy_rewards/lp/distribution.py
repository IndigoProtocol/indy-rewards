import datetime

from .. import analytics_api, time_utils
from ..models import (
    IAsset,
    IAssetReward,
    IndividualReward,
    LiquidityPoolReward,
    LiquidityPoolStatus,
)
from ..time_utils import get_reward_expiration
from . import saturation


def get_epoch_rewards_per_staker(
    epoch: int, epoch_indy: float
) -> list[IndividualReward]:
    def check_sum(rewards):
        indy_sum = sum(map(lambda x: x.get_indy_lovelaces(), rewards)) / 1_000_000.0
        if abs(epoch_indy - indy_sum) > 0.01:
            raise Exception(
                f"Lovelace based LP epoch sum: {indy_sum} "
                f"differs from nominal sum: {epoch_indy}"
            )

    days: list[datetime.date] = time_utils.get_epoch_snapshot_dates(epoch)
    rewards = []
    for day in days:
        rewards.extend(get_rewards_per_staker(day, epoch_indy))
    check_sum(rewards)
    return rewards


def get_rewards_per_staker(
    day: datetime.date, epoch_indy: float
) -> list[IndividualReward]:
    iassets_daily_rewards = get_iassets_daily_indy(day, epoch_indy)
    individual_rewards = distribute_to_accounts(day, iassets_daily_rewards)
    return individual_rewards


def get_iassets_daily_indy(day: datetime.date, epoch_indy: float) -> list[IAssetReward]:
    prices = analytics_api.get_iasset_ada_prices(day)
    total_supplies = analytics_api.get_iasset_supplies(day)
    dex_saturations = saturation.get_saturations(day)

    iasset_indy = _calculate_k(epoch_indy, dex_saturations, prices, total_supplies)

    return [IAssetReward(iasset=k, indy=v, day=day) for k, v in iasset_indy.items()]


def distribute_to_accounts(
    day: datetime.date, iassets_daily_rewards: list[IAssetReward]
) -> list[IndividualReward]:
    """Distribute rewards of each LP among individual LP token stakers.

    Args:
        pool_rewards: Liquidity pool rewards, to be further divided.
        staker_info: A nested dictionary containing staker information with iAsset names
            as keys, dictionaries of liquidity pools as values, and within each pool,
            dictionaries of stakers and their LP token stake amounts.

    Returns:
        A list of individual account PKH rewards.
    """
    lp_daily_status = analytics_api.get_lp_status(day)
    pool_rewards = distribute_to_liquidity_pools(
        iassets_daily_rewards, lp_daily_status, day
    )
    staker_info = analytics_api.get_account_staked_lp_tokens(day)

    individual_rewards = []
    for pr in pool_rewards:
        total_staked_lp_tokens: float = sum(staker_info[pr.lp].values())
        description = (
            f"Reward for providing {pr.lp.iasset.name} liquidity on {pr.lp.dex.name}"
        )
        for staker, staked_lp_tokens in staker_info[pr.lp].items():
            individual_rewards.append(
                IndividualReward(
                    pkh=staker,
                    indy=pr.indy * staked_lp_tokens / total_staked_lp_tokens,
                    day=pr.day,
                    description=description,
                    expiration=get_reward_expiration(pr.day),
                )
            )
    return individual_rewards


def distribute_to_liquidity_pools(
    iasset_rewards: list[IAssetReward],
    lp_statuses: list[LiquidityPoolStatus],
    day: datetime.date,
) -> list[LiquidityPoolReward]:
    pool_rewards = []
    for iasset_reward in iasset_rewards:
        pool_rewards.extend(
            _distribute_to_iasset_group(iasset_reward, lp_statuses, day)
        )
    return pool_rewards


def _distribute_to_iasset_group(
    iasset_reward: IAssetReward,
    lp_statuses: list[LiquidityPoolStatus],
    day: datetime.date,
) -> list[LiquidityPoolReward]:
    def sum_iasset(iasset: IAsset, lp_statuses: list[LiquidityPoolStatus]) -> float:
        return sum(st.iasset_balance for st in lp_statuses if st.lp.iasset == iasset)

    total_iasset_balance = sum_iasset(iasset_reward.iasset, lp_statuses)
    rewards = []
    for stat in lp_statuses:
        if stat.lp.iasset == iasset_reward.iasset:
            pool_reward = iasset_reward.indy * (
                stat.iasset_balance / total_iasset_balance
            )
            rewards.append(LiquidityPoolReward(indy=pool_reward, day=day, lp=stat.lp))
    return rewards


def _calculate_k(
    a: float, b: dict[IAsset, float], c: dict[IAsset, float], d: dict[IAsset, float]
) -> dict[IAsset, float]:
    """Calculate INDY tokens to be distributed to each iAsset LP group.

    Args:
        a: The total amount of INDY being distributed.
        b: A dictionary of each iAsset's liquidity saturation (phi) values.
        c: A dictionary of the relative daily close prices of the iAssets.
        d: A dictionary of the total supply of each iAsset.

    Returns:
        A dictionary of the calculated k values for each iAsset.

    Example:
        >>> calculate_k(
            4795,
            {IAsset(iUSD): 0.6, IAsset(iETH): 0.7, IAsset(iBTC): 0.8},
            {IAsset(iBTC): 60000, IAsset(iUSD): 2.7, IAsset(iETH): 4000},
            {IAsset(iETH): 1200, IAsset(iUSD): 4000000, IAsset(iBTC): 80})
        {IAsset(iUSD): 437.49, IAsset(iETH): 270.37, IAsset(iBTC): 250.65}
    """
    assets = list(b.keys())

    b_keys = set(b.keys())
    c_keys = set(c.keys())
    d_keys = set(d.keys())
    if b_keys != c_keys or c_keys != d_keys or b_keys != d_keys:
        raise Exception('"k" formula input dict key mismatch')

    m_values = [1 / b[asset] for asset in assets]
    m_sum = sum(m_values)
    m_normalized = {asset: m_value / m_sum for asset, m_value in zip(assets, m_values)}

    o_values = [c[asset] * d[asset] for asset in assets]
    o_sum = sum(o_values)
    o_normalized = {asset: o_value / o_sum for asset, o_value in zip(assets, o_values)}

    k_values = {
        asset: (a / 5) * ((m_normalized[asset] + o_normalized[asset]) / 2)
        for asset in assets
    }

    return k_values
