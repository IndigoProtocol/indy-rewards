import datetime
import gzip
import json
import urllib.request

import jsonschema


def get_indy_ada_daily_closing_prices() -> dict[datetime.date, float]:
    """Return all daily closing prices of INDY, denominated in ADA.

    Closing price for e.g. 2023-03-25 is the price at 2023-03-26 00:00.
    """
    ada_usd = get_ada_usd_daily_closing_prices()
    indy_usd = get_indy_usd_daily_closing_prices()
    indy_ada = {}
    for date in indy_usd.keys():
        if date in ada_usd.keys():
            indy_ada[date] = indy_usd[date] / ada_usd[date]
        else:
            raise Exception(f"Found INDY USD price for {date}, but no ADA USD price.")
    return indy_ada


def get_ada_usd_daily_closing_prices() -> dict[datetime.date, float]:
    return _get_daily_usd_prices(975)


def get_indy_usd_daily_closing_prices() -> dict[datetime.date, float]:
    return _get_daily_usd_prices(28303)


def _get_daily_usd_prices(asset_id: int) -> dict[datetime.date, float]:
    raw = _get_chart_data(asset_id)
    usd_prices: dict[datetime.date, float] = {}
    for x in raw["stats"]:
        timestamp = x[0] / 1000.0
        dt = datetime.datetime.utcfromtimestamp(timestamp)
        dt_zero_time = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        minus_one_date = dt.date() - datetime.timedelta(days=1)
        if dt == dt_zero_time:
            # We're technically interested in closing prices of dates, but Coingecko
            # prices are opening prices for the next day. Which is the same price,
            # with an offset date.
            usd_prices[minus_one_date] = x[1]
        else:
            # There's a window after UTC 00:00, e.g. 00:26, when the price for 00:00
            # isn't separately included yet. In that case, fill it out with the current
            # price.
            if minus_one_date not in usd_prices:
                usd_prices[minus_one_date] = x[1]

            # Add the latest price. This is a bit of a hack. The only price with a
            # time other than 00:00 is the current price. The current price is needed
            # for some commands in case they're executed for the current day, after
            # 21:46 (after the Indigo snapshot) but before 00:00 UTC (daily closing
            # price availability). Appending the current price here avoids an extra
            # network request.
            usd_prices[dt.date()] = x[1]

    return usd_prices


def _get_chart_data(asset_id: int) -> dict:
    """Return daily opening prices and volumes for an asset.

    Uses an undocumented Coingecko API, which seems more efficient and easy than the
    official API. Gets years' worth of daily prices (and volumes) in a single HTTP
    request.
    """
    req = urllib.request.Request(
        f"https://www.coingecko.com/price_charts/{asset_id}/usd/max.json",
        headers={
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "accept-encoding": "gzip",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            ),
        },
    )

    with urllib.request.urlopen(req) as response:
        if response.info().get("Content-Encoding") == "gzip":
            decompressed_content = gzip.decompress(response.read())
        else:
            decompressed_content = response.read()
        decoded_content = decompressed_content.decode("utf-8")
        json_response = json.loads(decoded_content)

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "stats": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": [{"type": "integer"}, {"type": "number"}],
                },
            },
            "total_volumes": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": [{"type": "integer"}, {"type": "number"}],
                },
            },
        },
        "required": ["stats", "total_volumes"],
    }

    jsonschema.validate(json_response, schema)

    return json_response
