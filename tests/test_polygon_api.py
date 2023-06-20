import datetime
import json
from datetime import date

import pytest
import pytest_mock

from indy_rewards import polygon_api


@pytest.mark.parametrize(
    "first_day,last_day,expected",
    (
        # All of these daily closing prices are from
        # https://pro.kraken.com/app/trade/ada-usd
        (
            date(2023, 1, 7),
            date(2023, 1, 11),
            {
                date(2023, 1, 7): 0.277037,
                date(2023, 1, 8): 0.297078,
                date(2023, 1, 9): 0.316758,
                date(2023, 1, 10): 0.322340,
                date(2023, 1, 11): 0.322954,
            },
        ),
        (date(2023, 1, 13), date(2023, 1, 13), {date(2023, 1, 13): 0.345659}),
        (date(2023, 1, 13), None, {date(2023, 1, 13): 0.345659}),
        (
            date(2022, 12, 31),
            date(2023, 1, 1),
            {date(2022, 12, 31): 0.245296, date(2023, 1, 1): 0.249685},
        ),
    ),
)
def test_get_daily_closing_prices_normal(
    first_day, last_day, expected, mocker: pytest_mock.MockerFixture
):
    """Work normally."""
    mocker.patch(
        "indy_rewards.polygon_api._fetch_prices",
        wraps=mock_polygon_api_response_ada_usd,
    )
    actual = polygon_api.get_daily_closing_prices("X:ADAUSD", first_day, last_day)
    assert len(actual) == len(expected)
    for day in actual.keys():
        assert actual[day] == pytest.approx(expected[day], rel=0.002)


@pytest.mark.parametrize(
    "from_day,to_day",
    (
        (date(2009, 1, 3), date(2200, 12, 24)),
        (date(3000, 1, 5), date(3000, 3, 15)),
        (date(2517, 9, 27), date(2517, 12, 1)),
    ),
)
def test_get_daily_closing_prices_unfinished_day(from_day, to_day):
    """Fail for unfinished (future) days."""
    with pytest.raises(
        ValueError, match=r"Won't return price for unfinished day [\d\-]+"
    ):
        polygon_api.get_daily_closing_prices(
            "X:ADAUSD",
            from_day,
            to_day,
        )


def mock_polygon_api_response_ada_usd(ticker: str, first_day: date, last_day: date):
    """Hardcoded response for price query, with date filtering.

    https://api.polygon.io/v2/aggs/ticker/X:ADAUSD/range/1/day/2022-10-01/2023-01-31?apiKey=*
    """

    def millis_to_date(time_in_millis: int):
        time = datetime.datetime.utcfromtimestamp(time_in_millis / 1000.0)
        return date(time.year, time.month, time.day)

    with open(
        "tests/data/inputs/api.polygon.io-ada-usd-prices-2022-10-2023-01.json"
    ) as f:
        api_response = json.load(f)

    filtered_results = [
        candle
        for candle in api_response["results"]
        if millis_to_date(candle["t"]) >= first_day
        and millis_to_date(candle["t"]) <= last_day
    ]

    day_count = len(filtered_results)

    api_response.update(
        {
            "results": filtered_results,
            "queryCount": day_count,
            "resultsCount": day_count,
            "count": day_count,
        }
    )

    return api_response
