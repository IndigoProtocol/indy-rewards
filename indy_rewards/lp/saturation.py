import datetime
from collections import defaultdict

from .. import analytics_api
from ..models import IAsset, LiquidityPoolStatus


def get_saturations(day: datetime.date) -> dict[IAsset, float]:
    unified_dex_info = analytics_api.get_lp_status(day)
    dex_balances = _sum_by_iasset(unified_dex_info)
    total_supplies = analytics_api.get_iasset_supplies(day)
    dex_saturations = _calculate_saturation_ratios(dex_balances, total_supplies)
    return dex_saturations


def _sum_by_iasset(lp_statuses: list[LiquidityPoolStatus]) -> dict[IAsset, float]:
    result: dict[IAsset, float] = defaultdict(float)
    for stat in lp_statuses:
        if stat.lp.other_asset_name != "ADA":
            raise ValueError("LP's other asset must be 'ADA'")
        result[stat.lp.iasset] += stat.iasset_balance
    return result


def _calculate_saturation_ratios(
    dex_balances: dict[IAsset, float], total_supplies: dict[IAsset, float]
) -> dict[IAsset, float]:
    if set(dex_balances.keys()) != set(total_supplies.keys()):
        raise ValueError("Keys of the two input dicts don't match.")
    ratios = {}
    for key in dex_balances.keys():
        ratios[key] = dex_balances[key] / total_supplies[key]
    return ratios
