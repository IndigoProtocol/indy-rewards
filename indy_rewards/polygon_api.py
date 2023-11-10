import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Container, Optional

import dotenv

POLYGON_API_KEY: Optional[str] = None


def get_daily_closing_prices(
    ticker: str,
    first_day: datetime.date,
    last_day: Optional[datetime.date] = None,
) -> dict[datetime.date, float]:
    """Returns a dictionary containing a range of daily closing prices.

    For assets that trade 24/7 the term "closing price" might feel ambiguous.
    The daily closing price for e.g. 2023-03-27 is the closing price for the
    (UTC) daily candle. Can also be defined as the opening price for the very
    start of the next day, the opening price for 2023-03-28 00:00 UTC.

    Args:
        ticker: Ticker symbol that api.polygon.io accepts,
            e.g. "X:ADAUSD", "X:BTCUSD".
        first_day: First day (UTC) to get a daily price for, inclusive.
            Can't be an unfinished day (UTC today or the future).
        last_day: Last day (UTC) to get a daily price for, inclusive.
            Can be omitted to query only a single day (first_day).
            Can't be before first_day, but can be first_day itself.
            Can't be an unfinished day.

    Returns:
        Dictionary containing daily closing prices mapped to datetime.date
        objects. The keys are UTC dates defined by a year, month and day.

        For example, for these args:

            ticker="X:ADAUSD"
            first_day=datetime.date(2023, 3, 8)
            last_day=datetime.date(2023, 3, 11)

        We get this result:

            {
                datetime.date(2023, 3, 8): 0.3176,
                datetime.date(2023, 3, 9): 0.3104,
                datetime.date(2023, 3, 10): 0.316,
                datetime.date(2023, 3, 11): 0.3074,
            }

        Which means the closing price for e.g. 2023 March 9 UTC was 0.3104,
        which is the same as the (opening) price at 2023 March 10 00:00 UTC.
    """

    if not last_day:
        last_day = first_day

    if first_day > last_day:
        raise ValueError(
            f"first_day ({first_day}) can't be after last_day ({last_day})"
        )

    if _is_unfinished_day(first_day):
        raise ValueError(f"Won't return price for unfinished day {first_day}")

    if _is_unfinished_day(last_day):
        raise ValueError(f"Won't return price for unfinished day {last_day}")

    response = _fetch_prices(ticker, first_day, last_day)

    closing_prices = _process_api_response(response)

    missing = _get_first_missing_date(closing_prices.keys(), first_day, last_day)

    if missing:
        raise Exception(
            f"Requested date range {first_day} to {last_day}, "
            f"but at least {missing} is missing"
        )

    return closing_prices


def load_api_key():
    global POLYGON_API_KEY
    dotenv.load_dotenv()
    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")


def _fetch_prices(
    ticker: str,
    first_day: datetime.date,
    last_day: datetime.date,
) -> dict:  # pragma: no cover
    if not POLYGON_API_KEY:
        load_api_key()
        if not POLYGON_API_KEY:
            raise Exception("POLYGON_API_KEY not set")

    params = urllib.parse.urlencode({"apiKey": POLYGON_API_KEY})

    url = urllib.parse.urljoin(
        "https://api.polygon.io",
        f"/v2/aggs/ticker/{ticker}/range/1/day/{first_day}/{last_day}?" + params,
    )

    req = urllib.request.Request(url)

    with urllib.request.urlopen(req) as response:
        response_body = json.loads(response.read())
        return response_body


def _process_api_response(response_body: dict) -> dict[datetime.date, float]:
    """Takes a api.polygon.io response, returns closing price dict."""

    res = response_body

    if "status" not in res or res["status"] != "OK":
        raise Exception(f"\"status\" in API response isn't \"OK\": {res['status']}")

    if res["queryCount"] != res["resultsCount"]:
        raise Exception(
            f"queryCount ({res['queryCount']}) "
            f"differs from resultsCount ({res['resultsCount']})"
        )

    if res["resultsCount"] == 0 or "results" not in res:
        raise Exception("No prices found in API response")

    closing_prices = {}

    for daily_candle in res["results"]:
        day_start_unix_millis = daily_candle["t"]
        daily_closing_price = daily_candle["c"]

        day_start_utc_time = datetime.datetime.utcfromtimestamp(
            day_start_unix_millis / 1000
        )

        if day_start_utc_time.time() != datetime.time.min:
            raise Exception(
                "Unexpected timestamp for daily candle (time not 00:00), "
                f"timestamp: {day_start_unix_millis}, "
                f"date: {day_start_utc_time.isoformat()}"
            )

        closing_prices[day_start_utc_time.date()] = daily_closing_price

    return closing_prices


def _get_first_missing_date(
    days: Container[datetime.date],
    first_day: datetime.date,
    last_day: datetime.date,
) -> None | datetime.date:
    """Verifies that consecutive dates between "first_day" and "last_day" (both
    inclusive) are present in "days".

    Returns:
        - "None" if there aren't any days missing.
        - The first missing date if there is one.
    """
    if last_day < first_day:
        first_day, last_day = last_day, first_day

    date = first_day

    while date <= last_day:
        if date not in days:
            return date
        date += datetime.timedelta(days=1)

    return None


def _is_unfinished_day(day: datetime.date) -> bool:
    """Check if 'day' (a UTC date) has passed yet.

    E.g. day 2023-03-29 is considered finished if it's currently 2023-03-30 00:00 UTC or
    later.
    """
    today_date = datetime.datetime.utcnow().date()
    return day >= today_date
