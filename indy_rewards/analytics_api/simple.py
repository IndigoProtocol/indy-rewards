"""More convenient interface to the Indigo analytics API."""

import datetime
import json
from collections import defaultdict
from typing import Callable, Optional

from .. import time_utils
from ..models import Dex, IAsset, LiquidityPool, LiquidityPoolStatus
from . import raw as raw_api


def get_iasset_ada_prices(day: datetime.date) -> dict[IAsset, float]:
    unix_time = time_utils.get_snapshot_unix_time(day)
    prices = raw_api.asset_prices(unix_time)
    return {IAsset.from_str(x["asset"]): x["price"] / 1_000_000.0 for x in prices}


def get_iasset_supplies(day: datetime.date) -> dict[IAsset, float]:
    snapshot_unix_time = time_utils.get_snapshot_unix_time(day)

    cdps = raw_api.cdps(snapshot_unix_time)

    def sum_minted_amounts(lst):
        sums = {}
        for d in lst:
            asset = IAsset.from_str(d["asset"])
            minted_amount = d["mintedAmount"]
            if asset in sums:
                sums[asset] += minted_amount
            else:
                sums[asset] = minted_amount
        return {asset: amount / 1_000_000.0 for asset, amount in sums.items()}

    total_supplies = sum_minted_amounts(cdps)

    return total_supplies


def get_iasset_ada_market_caps(day: datetime.date) -> dict[IAsset, float]:
    supplies = get_iasset_supplies(day)
    prices = get_iasset_ada_prices(day)
    iassets = supplies.keys()
    if set(iassets) != set(prices.keys()):
        raise Exception("iAsset supply and price keys don't match")
    return {x: supplies[x] * prices[x] for x in iassets}


def get_stability_pool_iasset_supplies(day: datetime.date) -> dict[IAsset, float]:
    unix_time = time_utils.get_snapshot_unix_time(day)
    sp_accounts = raw_api.rewards_stability_pool(unix_time)

    result: dict[IAsset, float] = {}
    for x in sp_accounts:
        asset = IAsset.from_str(x["asset"])
        staked = x["iasset_staked"] / 1e6
        if asset in result:
            result[asset] += staked
        else:
            result[asset] = staked

    return result


def get_stability_pool_saturations(day: datetime.date) -> dict[IAsset, float]:
    """Returns saturation ratios for stability pools.

    Examples:
        >>> get_stability_pool_saturations(datetime.date(2023, 4, 27))
        {'iBTC': 0.8449178811399581,
         'iETH': 0.8507158550985185,
         'iUSD': 0.5241037610939072}
    """
    sp = get_stability_pool_iasset_supplies(day)
    total = get_iasset_supplies(day)

    if set(sp.keys()) != set(total.keys()):
        raise ValueError("Keys don't match")

    ratios = {key: sp[key] / total[key] for key in sp.keys()}
    return ratios


def get_lp_status(
    day: datetime.date, with_lp_token_supplies: bool = False
) -> list[LiquidityPoolStatus]:
    unified_lp_info = _fetch_lp_statuses(day)

    if with_lp_token_supplies:
        lp_token_circ_supplies: Optional[
            dict[str, int]
        ] = get_lp_token_circulating_supplies(day)
        lp_token_staked_supplies: Optional[
            dict[str, int]
        ] = get_staked_lp_token_supplies(day)

        _validate_staked_lp_tokens(unified_lp_info, lp_token_staked_supplies)
    else:
        lp_token_circ_supplies = lp_token_staked_supplies = None

    pools: list[LiquidityPoolStatus] = []

    for lp in unified_lp_info:
        if lp["assetA"] == "ADA":
            raise Exception()
        if lp["assetB"] != "ADA":
            raise Exception()

        dt = datetime.datetime.utcfromtimestamp(lp["timestamp"])
        if dt.date() != day:
            raise Exception("LP entry's date doesn't match requested date")

        if with_lp_token_supplies:
            lp_token_circ_supply = (
                lp_token_circ_supplies[lp["token"]]
                if lp_token_circ_supplies is not None
                else None
            )
            lp_token_staked = (
                lp_token_staked_supplies[lp["token"]]
                if lp_token_staked_supplies is not None
                else None
            )

            if lp_token_staked is not None and lp_token_circ_supply is not None:
                if lp_token_staked > lp_token_circ_supply:
                    raise Exception(
                        f"More staked LP tokens ({lp_token_staked}) "
                        f"than circulating supply ({lp_token_circ_supply})"
                    )
        else:
            lp_token_circ_supply = lp_token_staked = None

        new_lp = LiquidityPool(
            dex=Dex.from_str(lp["exchange"]),
            iasset=lp["assetA"],
            lp_token_id=lp["token"],
            other_asset_name=lp["assetB"],
        )

        new_status = LiquidityPoolStatus(
            lp=new_lp,
            iasset_balance=lp["amount"] / 1_000_000,
            lp_token_circ_supply=lp_token_circ_supply,
            lp_token_staked=lp_token_staked,
            timestamp=dt,
        )

        pools.append(new_status)

    # TODO: Use a config for LP active periods instead of delist magic.
    if day > datetime.date(2023, 5, 30):
        pools = list(filter(lambda x: x.lp.dex.name.lower() != "muesliswap", pools))

    return pools


def get_staked_lp_token_supplies(day: datetime.date) -> dict[str, int]:
    """Get LP token supplies staked to Indigo for a given day.

    Returns:
        Dict with policy_id.asset_name LP identifier keys and Indigo-staked LP token
        values.

    Example:
        >>> get_staked_lp_token_supplies(2023, 5, 26)
        {'026a…a570.4520…2fc3': 2363212672220,
         '026a…a570.562b…b6e9': 4009215666,
         '026a…a570.63a3…ef2e': 2200016270,
         'af3d…557f.943b…1181': 2908892,
         'af3d…557f.b4bc…6b21': 14223650385,
         'e421…1d86.00cf…5b41': 581027770,
         'e421…1d86.8fde…fe47': 2236354278931,
         'e421…1d86.c42f…0e66': 270617652}
    """
    per_account_staked = _fetch_account_staked_lp_tokens(day)
    tokens_staked: dict[str, int] = defaultdict(int)
    for _, lp_tokens_staked in per_account_staked.items():
        for token_id, staked_token_count in lp_tokens_staked.items():
            tokens_staked[token_id] += staked_token_count
    return tokens_staked


def get_account_staked_lp_tokens(
    day: datetime.date,
) -> dict[LiquidityPool, dict[str, float]]:
    staked_lp = _fetch_account_staked_lp_tokens(day)
    dexes = get_lp_status(day)
    return _organize_staked_lp_tokens(staked_lp, dexes)


def get_lp_token_circulating_supplies(day: datetime.date) -> dict[str, int]:
    """Get LP token circulating supplies."""
    raw_total_supplies = _get_entries_for_day(
        raw_api.liquidity_pools_circulating_supply, day
    )

    total_supplies: dict[str, int] = {}
    for x in raw_total_supplies:
        if x["asset"] in total_supplies.keys():
            raise Exception("Double entry for the same LP token for the same day")
        total_supplies[x["asset"]] = x["amount"]

    mixed_stuff = _get_entries_for_day(raw_api.liquidity_pools_locked_asset, day)

    # These are out of circulation addresses and LP token amounts that need to be
    # excluded from the total supply to get the circulating supply.
    to_exclude = [
        x
        for x in mixed_stuff
        if not x["lp_token"] or x["for"].endswith(" Token Locked")
    ]

    # Not all WR LP tokens are present in the API data, so we'll set this hard-coded
    # amount where it's missing.
    wingriders_supply_magic = 9223372036854775000
    wingriders_constant_product_policy_id = (
        "026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570"
    )

    circ_supplies = total_supplies
    for x in to_exclude:
        asset_id = x["asset"]
        if asset_id not in circ_supplies.keys():
            if asset_id.startswith(wingriders_constant_product_policy_id + "."):
                circ_supplies[asset_id] = wingriders_supply_magic
            else:
                raise Exception("Want to exclude LP token, but no match")
        # Exclude special addres balance from total supply.
        circ_supplies[asset_id] -= x["amount"]

    return circ_supplies


def _fetch_lp_statuses(day: datetime.date) -> list[dict]:
    """Fetches LP status snapshots from Indigo Analytics /liquidity-pools/locked-asset.

    Only returns LP pairs that were at some point whitelisted on Indigo.

    Args:
        day: The day we'd like historical data for. Time of the snapshot is 21:46 UTC.

    Returns:
        List of dicts, with these keys:

        - amount: The amount of total iAsset of "lp_token" type in the pool
            at "timestamp", in lovelaces. In terms of iAsset, not LP token count.
            For example, if the LP has a total balance of 100 iETH, but only 25% of the
            LP tokens staked to Indigo, "amount" will be 100 (not 25).
        - assetA
        - assetB
        - exchange
        - timestamp: POSIX time of the snapshot.
        - token: LP token ID, in the format "policy_id.asset_name".
        - updated_at: Database record last update's date and time.

        For example:

            [{'amount': 2335283614237,
              'assetA': IAsset(iUSD),
              'assetB': 'ADA',
              'exchange': 'WingRiders',
              'timestamp': 1681335962,
              'token': '026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570.'
                  '452089abb5bf8cc59b678a2cd7b9ee952346c6c0aa1cf27df324310a70d02fc3',
              'updated_at': '2023-04-12T21:46:02.000000Z'}]

            Meaning there's a total of 2.335 million iUSD in that liquidity pool.
    """
    liquidity_pools = raw_api.liquidity_pools()
    mixed_stuff = _get_entries_for_day(raw_api.liquidity_pools_locked_asset, day)

    # Explicitly remove LP token entries. These don't hold iAsset lovelaces in "amount",
    # but LP token holdings of select addresses instead.
    dex_iassets = [
        x
        for x in mixed_stuff
        if x["lp_token"] and not x["for"].endswith(" Token Locked")
    ]

    def unify_lp_info(liquidity_pool, dex_iassets):
        unified_elements = []

        for lp_token in dex_iassets:
            for pool in liquidity_pool:
                if lp_token["lp_token"] == pool["token"]:
                    unified_elements.append(
                        {
                            "assetA": IAsset.from_str(pool["assetA"]),
                            "assetB": pool["assetB"],
                            "exchange": pool["exchange"],
                            "timestamp": lp_token["timestamp"],
                            "token": lp_token["lp_token"],
                            "updated_at": lp_token["updated_at"],
                            "amount": lp_token["amount"],
                        }
                    )

        return unified_elements

    unified_dex_info = unify_lp_info(liquidity_pools, dex_iassets)

    return unified_dex_info


def _fetch_account_staked_lp_tokens(day: datetime.date) -> dict[str, dict[str, int]]:
    """
    Returns:
        Dict of accounts and how much LP tokens they have staked on Indigo.

        For example:
            {'73a2…27ee': {'026a…a570.4520…2fc3': 3529050477441,
                           '026a…a570.63a3…ef2e': 2004842135},
             'e8aa…fdb9': {'e421…1d86.00cf…5b41': 881697}}

        Where:
            - 73a2…27ee and e8aa…fdb9 are Indigo accounts (payment key hashes in hex).
            - 026a…a570 is the WingRiders constant product LP contract's policy ID.
            - 4520…2fc3 is the WingRiders iUSD/ADA constant product pair LP token's
                asset name.
            - 3,529,050,477,441 is the amount of WR iUSD/ADA LP tokens that account
                73a2…27ee has staked in the Indigo LP locking smart contract.
            - 63a3…ef2e is the WingRiders iBTC/ADA constant product pair LP token's
                asset name.
            - e421…1d86 is the Minswap LP contract's policy ID.
            - 00cf…5b41 is the Minswap iBTC/ADA pair LP token's asset name.
    """
    unix_time = time_utils.get_snapshot_unix_time(day)
    staked_lp_tokens_raw = raw_api.liquidity_positions(unix_time)

    def to_dict(account_list):
        out_dict = {}
        for acc in account_list:
            value_dict = json.loads(acc["value"])
            for k, v in value_dict.items():
                if k != "lovelace":
                    owner_dict = out_dict.setdefault(acc["owner"], {})
                    owner_dict[k] = int(v)
        return out_dict

    return to_dict(staked_lp_tokens_raw)


def _organize_staked_lp_tokens(
    staked_lp_tokens, lp_statuses: list[LiquidityPoolStatus]
) -> dict[LiquidityPool, dict[str, float]]:
    """
    Returns:
        {LiquidityPool(dex=Dex(Minswap), iasset=IAsset(iETH), ...):
          {'staker1': 50000, 'staker2': 35000, 'staker3': 3}
         LiquidityPool(dex=Dex(Minswap), iasset=IAsset(iUSD), ...):
          {'staker1': 40000, 'staker2': 60000, 'staker3': 10000}}
    """
    lps: list[LiquidityPool] = list(map(lambda x: x.lp, lp_statuses))

    if len(lp_statuses) < 1:
        return {}

    day = lp_statuses[0].timestamp.date()
    for s in lp_statuses:
        if s.timestamp.date() != day:
            raise Exception("LP status dates don't match")

    staker_info: dict[LiquidityPool, dict[str, float]] = defaultdict(dict)
    for staker, tokens in staked_lp_tokens.items():
        for token, amount in tokens.items():
            # Special accommodation for the Muesli delist, as the API gives no
            # indication of that.
            # TODO: Use a config for LP active periods instead of delist magic.
            muesliswap_lp_v2_policy = (
                "af3d70acf4bd5b3abb319a7d75c89fb3e56eafcdd46b2e9b57a2557f"
            )
            muesli_last_day = datetime.date(2023, 5, 30)
            if (
                token.startswith(f"{muesliswap_lp_v2_policy}.")
                and day > muesli_last_day
            ):
                continue

            lp = _get_lp_for_token(token, lps)
            staker_info[lp][staker] = amount

    return staker_info


def _get_lp_for_token(token: str, lps: list[LiquidityPool]) -> LiquidityPool:
    for lp in lps:
        if lp.lp_token_id == token:
            return lp
    raise Exception(f"LP not found for LP token {token}")


def _get_entries_for_day(
    func: Callable[[float], list[dict]], day: datetime.date
) -> list[dict]:
    """Filter API responses where the API doesn't provide an upper time limit."""
    timestamp = time_utils.get_snapshot_unix_time(day)
    with_future = func(timestamp)
    day_only = [x for x in with_future if x["timestamp"] < timestamp + 20 * 3600]
    for x in day_only:
        if datetime.datetime.utcfromtimestamp(x["timestamp"]).date() != day:
            raise Exception("Date in entry doesn't match requested date")
    return day_only


def _validate_staked_lp_tokens(
    unified_lp_info: list[dict], lp_staked: Optional[dict[str, int]]
) -> None:
    if lp_staked is None:
        raise Exception("lp_staked is None, can't validate")
    lp_all_token_ids = set(map(lambda x: x["token"], unified_lp_info))
    lp_staked_token_ids = set(lp_staked.keys())
    if lp_all_token_ids != lp_staked_token_ids:
        # This can happen legitimately if there's a whitelisted LP that nobody
        # stakes tokens for, but that's less likely than an analytics API bug.
        raise Exception("Token IDs don't match for known LP tokens vs staked LP tokens")
