import datetime
import urllib.parse
from typing import Any, Callable, Optional, Sequence

import pandas as pd
import pytest
import requests
import requests_mock
from pandas.testing import assert_frame_equal
from pytest_mock.plugin import MockerFixture

from indy_rewards import sp
from indy_rewards.models import IAsset, IAssetReward


def test_get_rewards_per_pool_normal(mocker: MockerFixture):
    date = datetime.date(2023, 5, 17)

    expected = [
        IAssetReward(2405.498023, date, IAsset.iUSD),
        IAssetReward(1695.671994, date, IAsset.iBTC),
        IAssetReward(1652.429982, date, IAsset.iETH),
    ]

    get_rewards_per_pool_generic_test(date, expected, mocker)


def test_get_rewards_per_pool_mixed_new_old(mocker: MockerFixture):
    date = datetime.date(2023, 1, 7)

    expected = [
        IAssetReward(2930.073005, date, IAsset.iUSD),
        IAssetReward(2093.678566, date, IAsset.iBTC),
        IAssetReward(729.848427, date, IAsset.iETH),
    ]

    get_rewards_per_pool_generic_test(date, expected, mocker)


def test_get_rewards_per_pool_new_only(mocker: MockerFixture):
    date = datetime.date(2022, 11, 27)

    expected = [
        IAssetReward(2193.887259, date, IAsset.iUSD),
        IAssetReward(3559.712740, date, IAsset.iBTC),
    ]

    get_rewards_per_pool_generic_test(date, expected, mocker)


@pytest.mark.parametrize(
    "epoch, timestamps",
    [
        (
            378,
            (1669585500, 1669671900, 1669758300, 1669844700, 1669931100),
        ),
        (
            378,
            (1669585500, 1669671900, 1669758300, 1669844700, 1669931100),
        ),
        (
            379,
            (1670017500, 1670103900, 1670190300, 1670276700, 1670363100),
        ),
        (
            386,
            (1673041500, 1673127900, 1673214300, 1673300700, 1673387100),
        ),
    ],
)
def test_old_sp_distribution(
    epoch: int,
    timestamps: Sequence[int],
    mocker: MockerFixture,
    requests_mock: requests_mock.Mocker,
):
    def sort(df):
        return df.sort_values(by=["Period", "Address", "Purpose", "Date"]).reset_index(
            drop=True
        )

    mocker.patch(
        "indy_rewards.sp.distribution.volatility.get_all_volatilities",
        wraps=mocked_get_all_volatilities_off_by_one,
    )
    requests_mock.add_matcher(api_post_timestamp_matcher(epoch, "/api/cdps", "cdps-"))
    requests_mock.add_matcher(
        api_post_timestamp_matcher(epoch, "/api/asset-prices", "asset-prices-")
    )

    for t in timestamps:
        sp_resp = pd.read_csv(f"tests/data/inputs/{epoch}/rewards-sp-{t}.csv").to_dict(
            orient="records"
        )

        requests_mock.get(
            "https://analytics.indigoprotocol.io"
            f"/api/rewards/stability-pool?timestamp={t}.0",
            complete_qs=True,
            json=sp_resp,
        )

    result = sp.get_epoch_rewards_per_staker(epoch, 28768)
    result_df = sort(pd.DataFrame([x.as_dict() for x in result])).drop(
        "AvailableAt", axis=1
    )

    assert requests_mock.called
    sp.distribution.volatility.get_all_volatilities.assert_called()  # type: ignore

    expected = sort(pd.read_csv(f"tests/data/expected-outputs/{epoch}-sp.csv"))
    expected["Expiration"] = expected["Expiration"] + " 21:45"
    expected["Date"] = pd.to_datetime(expected["Date"]).dt.date

    assert_frame_equal(result_df, expected, atol=2, rtol=0)


def mocked_get_all_volatilities_off_by_one(day: datetime.date) -> dict[IAsset, float]:
    """Mock old volatility results."""
    return mocked_get_all_volatilities(day - datetime.timedelta(days=1))


def mocked_get_all_volatilities(day: datetime.date) -> dict[IAsset, float]:
    raw_vols = pd.read_csv("tests/data/inputs/volatility.csv")
    vols = raw_vols[raw_vols["date"] == day.isoformat()]
    return {
        IAsset.from_str("i" + row["asset"]): row["value"] for _, row in vols.iterrows()
    }


def api_post_timestamp_matcher(
    epoch: int, url_path: str, json_prefix: str
) -> Callable[[Any], Optional[requests.Response]]:
    def generic_timestamp_matcher(
        request: Any,
    ) -> Optional[requests.Response]:
        if request.url != urllib.parse.urljoin(
            "https://analytics.indigoprotocol.io", url_path
        ):
            return None

        timestamp = round(request.json().get("timestamp"))

        with open(
            f"tests/data/inputs/{epoch}/{json_prefix}{timestamp}.json",
            mode="rb",
        ) as f:
            resp = requests.Response()
            resp.status_code = 200
            resp._content = f.read()

        return resp

    return generic_timestamp_matcher


def get_rewards_per_pool_generic_test(
    date: datetime.date, expected: list[IAssetReward], mocker: MockerFixture
):
    mocker.patch(
        "indy_rewards.sp.distribution.volatility.get_all_volatilities",
        wraps=mocked_get_all_volatilities,
    )
    has_stakers = set(map(lambda x: x.iasset, expected))
    result = sp.get_rewards_per_pool(date, 28768, has_stakers)
    compare_pool_distributions(result, expected)


def compare_pool_distributions(a: list[IAssetReward], b: list[IAssetReward]):
    def _date_check(rewards):
        date_set = {x.day for x in rewards}
        assert len(date_set) == 1

    assert len(a) == len(b)
    assert a[0].day == b[0].day
    _date_check(a)
    _date_check(b)

    a_dict = {x.iasset: x.indy for x in a}
    b_dict = {x.iasset: x.indy for x in b}

    assert set(a_dict.keys()) == set(b_dict.keys())
    for k in a_dict.keys():
        assert a_dict[k] == pytest.approx(b_dict[k], abs=1e-6)
