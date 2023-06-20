import datetime
import statistics
from typing import OrderedDict, Sequence

from . import config, polygon_api
from .models import IAsset

# This mapping needs to live somewhere, as we can't assume all future iAsset
# base asset tickers (stocks, commodities) will fit the X:{symbol}USD pattern.
IASSET_USD_TICKERS = {
    "ibtc": "X:BTCUSD",
    "ieth": "X:ETHUSD",
}


def get_volatility(iasset_symbol: str, day: datetime.date) -> float:
    """Returns the volatility factor for a given iAsset and date.

    Args:
        iasset_symbol: E.g. 'iUSD', 'iETH', 'iBTC', case insensitive.
        day: UTC day to calculate volatility for, which'll be based on
            the previous 365 UTC days' closing prices (but not this day's).

    Returns:
        The volatility coefficient for a given iAsset on a given date,
        which is the sigma value in the whitepaper.
    """

    # It's not clear what the whitepaper means by "tracked asset's  historical
    # closing price for the past year".
    #
    # What is a "year"? 365 days, e.g. 2023-03-03 .. 2024-03-01, or same month
    # and day in different years, e.g. 2023-03-01 .. 2024-03-01 (which is
    # usually 366 and in leap years 367 data points)? This function uses the
    # former, 365 days.
    #
    # When calculating rewards for e.g. the 2023-03-15 21:45 UTC daily snapshot
    # we'll use closing prices from these 365 UTC days, inclusive:
    # 2023-03-14 .. 2022-03-15.
    #
    # That's 365 price points, the last one being the closing price of the
    # UTC day *before* the day we're calculating for. That's because sometimes
    # this calculation is run before the closing price of the day is known,
    # right after 21:45 UTC, before the "closing" time of 00:00 UTC.

    last_day = day - datetime.timedelta(days=1)
    first_day = last_day - datetime.timedelta(days=365 - 1)

    iasset_symbol = iasset_symbol.lower()

    if iasset_symbol != "iusd" and iasset_symbol not in IASSET_USD_TICKERS:
        raise ValueError(f'Unknown iAsset "{iasset_symbol}"')

    if iasset_symbol == "iusd":
        # FIXME: It's incorrect to assume 1 iUSD = 1 USD like this.
        # iUSD isn't pegged to USD, but the median of USDC, USDT and TUSD.
        iasset_usd_prices = _get_ones(first_day, last_day)
    else:
        iasset_usd_prices = _order_by_date(
            polygon_api.get_daily_closing_prices(
                IASSET_USD_TICKERS[iasset_symbol], first_day, last_day
            )
        )

    ada_usd_prices = _order_by_date(
        polygon_api.get_daily_closing_prices("X:ADAUSD", first_day, last_day)
    )

    iasset_ada_prices = tuple(
        iasset_usd_prices[date] / ada_usd_prices[date]
        for date in iasset_usd_prices.keys()
    )

    daily_pct_changes = _get_daily_pct_changes(iasset_ada_prices)
    sigma = statistics.pstdev(daily_pct_changes)
    return sigma


def get_all_volatilities(day: datetime.date) -> dict[IAsset, float]:
    iassets = config.get_active_iassets(day)
    return {x: get_volatility(x.name, day) for x in iassets}


def _get_daily_pct_changes(prices: Sequence[float]) -> tuple[float, ...]:
    """Returns percentage changes for a series.

    Args:
        prices: E.g. (100, 120, 60), assumes no element of "prices" is zero.

    Returns:
        Relative differences between prices, e.g. (0.2, -0.5).
    """
    return tuple((b - a) / a for a, b in zip(prices[::1], prices[1::1]))


def _order_by_date(
    prices: dict[datetime.date, float]
) -> OrderedDict[datetime.date, float]:
    return OrderedDict(sorted(prices.items(), key=lambda x: x))


def _get_ones(
    first_day: datetime.date, last_day: datetime.date
) -> OrderedDict[datetime.date, float]:
    if first_day > last_day:
        raise Exception()
    ret = OrderedDict()
    while first_day <= last_day:
        ret[first_day] = 1.0
        first_day += datetime.timedelta(days=1)
    return ret
