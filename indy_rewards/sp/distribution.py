import datetime
import statistics
from typing import Optional

from .. import analytics_api, config, time_utils, volatility
from ..models import IAsset, IAssetReward, IndividualReward


def get_epoch_rewards_per_staker(
    epoch: int, epoch_indy: float
) -> list[IndividualReward]:
    rewards = []
    for day in time_utils.get_epoch_snapshot_dates(epoch):
        rewards += get_rewards_per_staker(day, epoch_indy)
    return rewards


def get_rewards_per_staker(
    day: datetime.date, epoch_indy: float
) -> list[IndividualReward]:
    snapshot_timestamp = time_utils.get_snapshot_unix_time(day)
    all_accounts = analytics_api.raw.rewards_stability_pool(snapshot_timestamp)
    eligible_accounts = [x for x in all_accounts if _is_at_least_24h_old(x, day)]
    eligible_accounts = _merge_duplicate_accounts(eligible_accounts)
    iassets_with_stakers = _get_unique_iassets(eligible_accounts)

    rewards_per_pool = get_rewards_per_pool(day, epoch_indy, iassets_with_stakers)
    rewarded_iassets = list(map(lambda x: x.iasset, rewards_per_pool))

    _check_each_iasset_has_stakers(rewards_per_pool, eligible_accounts)
    _check_each_account_has_reward(rewarded_iassets, all_accounts)

    rewards = []

    for pool_reward in rewards_per_pool:
        iasset_accounts = {
            x["owner"]: x["iasset_staked"]
            for x in eligible_accounts
            if IAsset.from_str(x["asset"]) == pool_reward.iasset
        }
        comment = f"SP reward for {pool_reward.iasset.name}"
        rewards += _pro_rata_distribute(pool_reward.indy, iasset_accounts, day, comment)

    if len(rewards) != len(eligible_accounts):
        raise Exception(
            f"Accounts from API: {len(eligible_accounts)}, "
            f"but reward items: {len(rewards)}"
        )

    return rewards


def get_rewards_per_pool(
    day: datetime.date, epoch_indy: float, iassets_with_stakers: set[IAsset]
) -> list[IAssetReward]:
    saturations = analytics_api.get_stability_pool_saturations(day)
    market_caps = analytics_api.get_iasset_ada_market_caps(day)

    new_iassets = config.get_new_iassets(day)

    pool_weights = get_pool_weights(
        saturations, market_caps, day, new_iassets, iassets_with_stakers
    )

    daily_indy = epoch_indy / 5
    daily_pool_rewards = [
        IAssetReward(
            day=day,
            iasset=iasset,
            indy=(weight * daily_indy),
        )
        for iasset, weight in pool_weights.items()
    ]

    return daily_pool_rewards


def get_pool_weights(
    saturations: dict[IAsset, float],
    market_caps: dict[IAsset, float],
    day: datetime.date,
    new_iassets: set[IAsset],
    has_stakers: set[IAsset],
) -> dict[IAsset, float]:
    if day >= datetime.date(2024, 12, 5):
        return {
            IAsset.from_str("ibtc"): (3606.19 / 21189.77),
            IAsset.from_str("ieth"): (1176.91 / 21189.77),
            IAsset.from_str("iusd"): (15406.67 / 21189.77),
            IAsset.from_str("isol"): (1000.00 / 21189.77),
        }
    if day >= datetime.date(2024, 11, 26):
        return {
            IAsset.from_str("ibtc"): (2469.29 / 19664.35),
            IAsset.from_str("ieth"): (1504.89 / 19664.35),
            IAsset.from_str("iusd"): (14690.17 / 19664.35),
            IAsset.from_str("isol"): (1000.00 / 19664.35),
        }
    if day >= datetime.date(2024, 7, 14):
        return {
            IAsset.from_str("ibtc"): (2469.29 / 18664.35),
            IAsset.from_str("ieth"): (1504.89 / 18664.35),
            IAsset.from_str("iusd"): (14690.17 / 18664.35),
        }

    if day >= datetime.date(2023, 11, 6):
        return {
            IAsset.from_str("ibtc"): (3668 / 22431),
            IAsset.from_str("ieth"): (3188 / 22431),
            IAsset.from_str("iusd"): (15574 / 22431),
        }

    return get_pool_weights_before_epoch_448(
        saturations, market_caps, day, new_iassets, has_stakers
    )


def get_pool_weights_before_epoch_448(
    saturations: dict[IAsset, float],
    market_caps: dict[IAsset, float],
    day: datetime.date,
    new_iassets: set[IAsset],
    has_stakers: set[IAsset],
) -> dict[IAsset, float]:
    weights: dict[IAsset, float] = {}

    for iasset in saturations.keys():
        if iasset not in has_stakers:
            weights[iasset] = 0
            continue

        weights[iasset] = _calculate_weight(
            iasset,
            saturations,
            day,
            market_caps,
            new_iassets,
            has_stakers,
        )

        if weights[iasset] == 0:
            raise Exception(f"Zero weight for {iasset.name}")

    total = sum(weights.values())
    if abs(total - 1) > 1e-8:
        raise Exception(f"Sum of weights is not 1, it's {total}")

    return weights


def _validate_keys(
    saturations: dict[IAsset, float],
    market_caps: dict[IAsset, float],
    volatilities: Optional[dict[IAsset, float]] = None,
) -> None:
    sat_keys = set(saturations.keys())
    mcap_keys = set(market_caps.keys())
    if volatilities is not None:
        vol_keys = set(volatilities.keys())
        if sat_keys != mcap_keys or mcap_keys != vol_keys or sat_keys != vol_keys:
            raise ValueError("Keys don't match")
    else:
        if sat_keys != mcap_keys:
            raise ValueError("Keys don't match")


def _get_vol_inverse_sum(
    volatilities: dict[IAsset, float], has_stakers: set[IAsset]
) -> float:
    vol_inverse_sum = 0.0
    for iasset, vol in volatilities.items():
        if vol < 0:
            raise ValueError(f"Negative volatility: {vol}")
        elif vol == 0:
            raise ValueError(f"Zero volatility for {iasset}")
        else:
            if iasset in has_stakers:
                vol_inverse_sum += 1 / vol
    return vol_inverse_sum


def _get_sat_inverse_sum(saturations, has_stakers, new_iassets) -> float:
    sat_inverse_sum = 0.0
    for iasset, sat in saturations.items():
        if sat < 0 or sat > 1:
            raise ValueError(f"Invalid saturation for {iasset}: {sat}")
        elif iasset not in new_iassets and iasset in has_stakers:
            sat_inverse_sum += 1 / sat
    return sat_inverse_sum


def _get_mcap_sum(market_caps, new_iassets) -> float:
    mcap_sum = 0.0
    for iasset, mcap in market_caps.items():
        if mcap <= 0:
            raise ValueError(f"Market cap for {iasset} is zero or less: {mcap}")
        elif iasset not in new_iassets:
            mcap_sum += mcap
    return mcap_sum


def _get_volatility_term(
    iasset: IAsset, volatilities: dict[IAsset, float], has_stakers: set[IAsset]
) -> float:
    vol_inverse_sum = _get_vol_inverse_sum(volatilities, has_stakers)
    if vol_inverse_sum > 0 and iasset in has_stakers:
        return (1 / volatilities[iasset]) / vol_inverse_sum
    else:
        return 0


def _calculate_weight(
    iasset: IAsset,
    saturations: dict[IAsset, float],
    day: datetime.date,
    market_caps: dict[IAsset, float],
    new_iassets: set[IAsset],
    has_stakers: set[IAsset],
) -> float:
    saturation_term = 0.0
    market_cap_term = 0.0

    sat_inverse_sum = _get_sat_inverse_sum(saturations, has_stakers, new_iassets)
    mcap_sum = _get_mcap_sum(market_caps, new_iassets)

    if iasset not in new_iassets and iasset in has_stakers:
        saturation_term = (1 / saturations[iasset]) / sat_inverse_sum
        market_cap_term = market_caps[iasset] / mcap_sum

    # No more volatility factor under normal circumstances per governance vote #19.
    first_no_volatility_day = datetime.date(2023, 5, 26)
    use_volatility = (
        (day < first_no_volatility_day)
        or len(new_iassets) > 0
        or (sat_inverse_sum <= 0 or mcap_sum <= 0)
    )
    volatilities: Optional[dict[IAsset, float]] = None
    volatility_term: Optional[float] = None
    if use_volatility:
        volatilities = volatility.get_all_volatilities(day)
        volatility_term = _get_volatility_term(iasset, volatilities, has_stakers)
    _validate_keys(saturations, market_caps, volatilities)

    if sat_inverse_sum > 0 and mcap_sum > 0:
        if use_volatility:
            if volatility_term is None:
                raise Exception("Want to use volatility part, but it's None")
            if volatility_term <= 0:
                raise Exception(f"Volatility part is <= 0 (it's {volatility_term})")
            return statistics.mean((volatility_term, saturation_term, market_cap_term))
        else:
            return statistics.mean((saturation_term, market_cap_term))
    elif iasset in new_iassets:
        if volatility_term and volatility_term > 0:
            return volatility_term
        else:
            raise Exception("Would rely on volatility only, but it's <= 0")
    else:
        raise Exception(f"Can't determine stability pool weight for {iasset.name}")


def _check_each_iasset_has_stakers(
    stability_pool_rewards: list[IAssetReward], account_balances: list[dict]
) -> None:
    for r in stability_pool_rewards:
        if r.indy == 0:
            continue
        has_staker = False
        for a in account_balances:
            if a["asset"] == r.iasset.name:
                has_staker = True
        if not has_staker:
            raise Exception(
                f"{r.iasset.name} SP has {r.indy} INDY rewards, "
                f"but doesn't have stakers."
            )


def _merge_duplicate_accounts(account_balances: list[dict]) -> list[dict]:
    merged_accounts: dict[tuple[str, str], dict] = {}
    for account in account_balances:
        key = (account["owner"], account["asset"])
        if key in merged_accounts:
            merged_accounts[key]["iasset_staked"] += account["iasset_staked"]
        else:
            # Remove "opened_at" because it'd be ambiguous.
            new_account = {k: v for k, v in account.items() if k != "opened_at"}
            merged_accounts[key] = new_account

    return [
        {
            "owner": key[0],
            "asset": key[1],
            "iasset_staked": value["iasset_staked"],
        }
        for key, value in merged_accounts.items()
    ]


def _check_each_account_has_reward(
    rewarded_iassets: list[IAsset], account_balances: list[dict]
) -> None:
    for a in account_balances:
        iasset = IAsset.from_str(a["asset"])
        if iasset not in rewarded_iassets:
            raise Exception(f"{iasset.name} is SP staked, but can't get rewards")


def _pro_rata_distribute(
    indy_to_distribute: float,
    accounts: dict[str, float],
    day: datetime.date,
    comment: str,
) -> list[IndividualReward]:
    """Distributes INDY to accounts proportional to their individual shares, weights.

    Args:
        indy_to_distribute: Total INDY to distribute. Human INDY units, not lovelaces.
        accounts: Dict with owner PKHs as keys and weights as values. Weight can be any
            common unit, like staked INDY, staked iAsset, staked LP token.
        day: Day that the rewards are for.
        comment: Text description for the rewards.

    Returns:
        List of IndividualReward, one for each account.
    """
    total = sum(accounts.values())
    rewards = []
    for owner_pkh, weight in accounts.items():
        rewards.append(
            IndividualReward(
                indy=weight / total * indy_to_distribute,
                day=day,
                pkh=owner_pkh,
                expiration=time_utils.get_reward_expiration(day),
                description=comment,
            )
        )
    return rewards


def _get_unique_iassets(accounts: list[dict]) -> set[IAsset]:
    ret = set()
    for a in accounts:
        iasset = IAsset.from_str(a["asset"])
        ret.add(iasset)
    return ret


def _is_at_least_24h_old(account: dict, snapshot_day: datetime.date) -> bool:
    """Ignore iSOL accounts opened before 2024-11-27 (first day of asset
    whitelisting)."""
    if snapshot_day < datetime.date(2024, 11, 27) and account["asset"] == "iSOL":
        return True

    """Returns whether the SP account was opened within 24h relative to the snapshot."""
    snap = time_utils.get_snapshot_time(snapshot_day)
    open = datetime.datetime.utcfromtimestamp(account["opened_at"]).replace(
        tzinfo=datetime.timezone.utc
    )
    return open + datetime.timedelta(days=1) <= snap


def sp_epoch_emission(epoch: int) -> float:
    if epoch >= 526:
        return 21189.77
    if epoch >= 524:
        return 19664.35

    if epoch >= 497:
        return 18664.35

    if epoch >= 447:
        return 22431

    return 28768


def gov_epoch_emission(epoch: int) -> float:
    if epoch >= 529:
        return 5046.33

    if epoch >= 488:
        return 6046.11

    return 2398
