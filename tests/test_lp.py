import datetime
import os
import tempfile

import click.testing
import pandas as pd
import pytest

from indy_rewards.cli import lp as lp_command
from indy_rewards.lp.distribution import get_iassets_daily_indy


def test_old_k():
    result = get_iassets_daily_indy(datetime.date(2022, 12, 21), 4795)

    expected = {
        "iBTC": 303.606595,
        "iUSD": 655.393405,
    }

    result_iassets = map(lambda x: x.iasset.name, result)
    assert set(result_iassets) == set(expected.keys())
    for reward in result:
        assert round(reward.indy, 6) == expected[reward.iasset.name]


@pytest.mark.parametrize(
    "epoch,expected_output",
    (
        pytest.param(
            "399", "tests/data/expected-outputs/399-lp.csv", marks=pytest.mark.skip
        ),
        ("401", "tests/data/expected-outputs/401-lp.csv"),
    ),
)
def test_lp_cli_e2e(epoch: str, expected_output: str):
    def sort(df):
        return df.sort_values(by=["Period", "Address", "Purpose", "Date"]).reset_index(
            drop=True
        )

    expected = sort(pd.read_csv(expected_output))
    expected["Expiration"] = expected["Expiration"] + " 21:45"

    with tempfile.NamedTemporaryFile(delete=False) as temp:
        cli_result = click.testing.CliRunner().invoke(
            lp_command, [epoch, "--outfile", temp.name]
        )
        assert cli_result.exit_code == 0
        result = sort(pd.read_csv(temp.name)).drop("AvailableAt", axis=1)

    # Workaround for Windows.
    os.remove(temp.name)

    pd.testing.assert_frame_equal(result, expected, atol=1)


def test_k_vs_whitepaper():
    lp_epoch_indy = 4795

    result = get_iassets_daily_indy(datetime.date(2023, 3, 25), lp_epoch_indy)

    # These inputs for the "k" function were calculated based on the
    # whitepaper, and data from the same Indigo API endpoints that the lp
    # module uses.
    prices = {
        "iUSD": 2.852131,
        "iBTC": 78139.907274,
        "iETH": 4940.861058,
    }
    total_supplies = {
        "iUSD": 7071118.962576,
        "iBTC": 71.117697,
        "iETH": 1159.374502,
    }
    dex_saturations = {
        "iUSD": 0.32773456858060773,
        "iBTC": 0.13248473161328608,
        "iETH": 0.15528399554193406,
    }

    expected = calculate_k(lp_epoch_indy, dex_saturations, prices, total_supplies)

    result_iassets = map(lambda x: x.iasset.name, result)
    assert set(result_iassets) == set(expected.keys())

    for reward in result:
        assert reward.indy == pytest.approx(expected[reward.iasset.name], rel=1e-6)


# Based on the "k" formula in this version of the whitepaper:
# https://github.com/IndigoProtocol/paper/pull/8
def calculate_k(
    a: float, b: dict[str, float], c: dict[str, float], d: dict[str, float]
) -> dict[str, float]:
    """Calculate INDY tokens to be distributed to LP stakers of each iAsset.

    Args:
        a (float): The total amount of INDY being distributed.
        b (Dict[str, float]): A dictionary of each iAsset's liquidity saturation (phi).
        c (Dict[str, float]): A dictionary of the relative daily iAsset close prices.
        d (Dict[str, float]): A dictionary of the total supply of each iAsset.

    Returns:
        Dict[str, float]: A dictionary of the calculated k values for each iAsset.

    Example:
        >>> calculate_k(
            4795,
            {'iUSD': 0.6, 'iETH': 0.7, 'iBTC': 0.8},
            {'iBTC': 60000, 'iUSD': 2.7, 'iETH': 4000},
            {'iETH': 1200, 'iUSD': 4000000, 'iBTC': 80})
        {'iUSD': 437.49, 'iETH': 270.37, 'iBTC': 250.65}
    """
    assets = list(b.keys())

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
