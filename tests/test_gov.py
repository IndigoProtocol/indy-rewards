import os
import tempfile

import pandas as pd
from click.testing import CliRunner

from indy_rewards import cli


def test_gov_e2e():
    expected = pd.read_csv("tests/data/expected-outputs/379-gov.csv")
    expected["Expiration"] = expected["Expiration"] + " 21:45"

    with tempfile.NamedTemporaryFile(delete=False) as temp:
        cli_result = CliRunner().invoke(
            cli.gov, ["--indy", "2398", "379", "--outfile", temp.name]
        )
        assert cli_result.exit_code == 0
        result = pd.read_csv(temp.name).drop("AvailableAt", axis=1)
        pd.testing.assert_frame_equal(_sort(result), _sort(expected), atol=1, rtol=0)

    # On Windows the same file can't be opened for reading and writing at the same time,
    # that's why delete=False and manual remove is used.
    os.remove(temp.name)


def _sort(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(by=["Address"]).reset_index(drop=True)
