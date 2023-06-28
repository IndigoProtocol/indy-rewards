import datetime
import sys
from collections import defaultdict
from typing import Callable, Optional

import click
import pandas as pd

from indy_rewards import config
from indy_rewards import gov as gov_module
from indy_rewards import lp as lp_module
from indy_rewards import polygon_api
from indy_rewards import sp as sp_module
from indy_rewards import summary, time_utils, volatility
from indy_rewards.models import Dex, IAsset, IndividualReward, LiquidityPool


@click.group()
def rewards():
    pass


def pkh_option(function: Callable):
    return click.option(
        "--pkh", multiple=True, help="Filter by the start of one or more PKHs."
    )(function)


def outfile_option(function):
    return click.option("--outfile", "-o", type=click.Path(), help="Output CSV file.")(
        function
    )


def indy_option(indy_amount: int, name="--indy", help="INDY to distribute per epoch."):
    def decorator(function: Callable):
        return click.option(
            name,
            default=indy_amount,
            type=click.FLOAT,
            help=help,
            show_default=True,
        )(function)

    return decorator


def epoch_or_date_arg(function: Callable):
    arg = click.argument(
        "epoch_or_date",
        callback=validate_epoch_or_date_arg,
    )
    function.__doc__ = (
        function.__doc__ or ""
    ) + "\n\nEPOCH_OR_DATE: Epoch number, or a date in YYYY-MM-DD format."
    return arg(function)


def validate_epoch_or_date_arg(ctx, param, value):
    try:
        epoch = int(value)
        _error_on_future(epoch)
        return epoch
    except ValueError:
        try:
            date = datetime.datetime.strptime(value, "%Y-%m-%d").date()
            _error_on_future(date)
            return date
        except ValueError:
            raise click.BadParameter(
                "Must be a valid integer or date in the YYYY-MM-DD format."
            )


@rewards.command()
@indy_option(config.LP_EPOCH_INDY)
@pkh_option
@outfile_option
@epoch_or_date_arg
def lp(indy: float, pkh: tuple[str], outfile: str, epoch_or_date: int | datetime.date):
    """Print or save liquidity pool token staking rewards."""
    if isinstance(epoch_or_date, int):
        rewards = lp_module.get_epoch_rewards_per_staker(epoch_or_date, indy)
    else:
        rewards = lp_module.get_rewards_per_staker(epoch_or_date, indy)
    rewards = _pkh_filter(rewards, pkh)
    _output(rewards, outfile)


@rewards.command()
@indy_option(config.LP_EPOCH_INDY)
@epoch_or_date_arg
def lp_apr(indy: float, epoch_or_date: int | datetime.date):
    """Print LP token staking INDY-based APRs."""

    def display_aprs(lp_aprs: dict[LiquidityPool, float]):
        aprs_by_iasset: dict[IAsset, dict[Dex, float]] = defaultdict(dict)
        for lp, apr in lp_aprs.items():
            aprs_by_iasset[lp.iasset][lp.dex] = apr

        for iasset in sorted(aprs_by_iasset.keys(), key=lambda x: x.name):
            click.secho(f"\n{iasset.name}", fg="green", bold=True)
            dexes_sorted = sorted(aprs_by_iasset[iasset].keys(), key=lambda x: x.name)
            for dex in dexes_sorted:
                click.echo(f"{dex.name}: {aprs_by_iasset[iasset][dex] * 100:.2f}%")

    if isinstance(epoch_or_date, int):
        epoch = epoch_or_date
        date = None
    else:
        epoch = time_utils.date_to_epoch(epoch_or_date)
        date = epoch_or_date

    aprs = lp_module.get_epoch_aprs(epoch, indy, date)
    display_aprs(aprs)


@rewards.command()
@indy_option(config.GOV_EPOCH_INDY)
@pkh_option
@outfile_option
@click.argument("epoch", type=int)
def gov(indy: float, pkh: tuple[str], outfile: str, epoch: int):
    """Print or save INDY governance staking rewards.

    EPOCH: Epoch to get rewards for. Technically it's the epoch end snapshot that
    counts.
    """
    rewards = gov_module.get_epoch_rewards_per_staker(epoch, indy)
    rewards = _pkh_filter(rewards, pkh)
    _output(rewards, outfile)


@rewards.command()
@indy_option(config.SP_EPOCH_INDY)
@pkh_option
@outfile_option
@epoch_or_date_arg
def sp(
    indy: float,
    pkh: tuple[str],
    outfile: str,
    epoch_or_date: int | datetime.date,
):
    """Print or save stability pool staking rewards."""
    _load_polygon_api_key_or_fail(epoch_or_date)
    if isinstance(epoch_or_date, int):
        rewards = sp_module.get_epoch_rewards_per_staker(epoch_or_date, indy)
    else:
        rewards = sp_module.get_rewards_per_staker(epoch_or_date, indy)
    rewards = _pkh_filter(rewards, pkh)
    _output(rewards, outfile)


@rewards.command()
@indy_option(config.SP_EPOCH_INDY)
@epoch_or_date_arg
def sp_apr(indy: float, epoch_or_date: int | datetime.date):
    """Print SP staking INDY-based APRs."""

    if isinstance(epoch_or_date, int):
        aprs = sp_module.get_epoch_aprs(epoch_or_date, indy)
    else:
        aprs = sp_module.get_daily_aprs(epoch_or_date, indy)

    sps = sorted(aprs.keys(), key=lambda x: x.iasset.name)
    for sp in sps:
        click.echo(f"{sp.iasset.name}: {aprs[sp] * 100:.2f}%")


@rewards.command()
@pkh_option
@outfile_option
@epoch_or_date_arg
def all(pkh: tuple[str], outfile: str, epoch_or_date: int | datetime.date):
    """Print or save SP, LP and governance staking rewards."""
    _load_polygon_api_key_or_fail(epoch_or_date)

    if isinstance(epoch_or_date, int):
        rewards = summary.get_epoch_all_rewards(
            epoch_or_date,
            config.SP_EPOCH_INDY,
            config.LP_EPOCH_INDY,
            config.GOV_EPOCH_INDY,
        )
    else:
        rewards = summary.get_day_all_rewards(
            epoch_or_date,
            config.SP_EPOCH_INDY,
            config.LP_EPOCH_INDY,
            config.GOV_EPOCH_INDY,
        )

    rewards = _pkh_filter(rewards, pkh)
    _output(rewards, outfile)


@rewards.command(name="summary")
@indy_option(
    config.SP_EPOCH_INDY,
    "--sp-indy",
    "INDY to distribute to stability pool stakers per epoch.",
)
@indy_option(
    config.LP_EPOCH_INDY,
    "--lp-indy",
    "INDY to distribute to LP token stakers per epoch.",
)
@indy_option(
    config.GOV_EPOCH_INDY,
    "--gov-indy",
    "INDY to distribute to INDY governance stakers per epoch.",
)
@pkh_option
@epoch_or_date_arg
def summary_command(
    sp_indy: float,
    lp_indy: float,
    gov_indy: float,
    pkh: tuple[str],
    epoch_or_date: int | datetime.date,
):
    """Print summary of all rewards for a given epoch."""
    _load_polygon_api_key_or_fail(epoch_or_date)

    if isinstance(epoch_or_date, int):
        epoch_rewards = summary.get_epoch_all_rewards(
            epoch_or_date,
            sp_indy,
            lp_indy,
            gov_indy,
        )
        epoch_rewards = _pkh_filter(epoch_rewards, pkh)
        sum_table = summary.get_summary(epoch_rewards)
    else:
        day_rewards = summary.get_day_all_rewards(
            epoch_or_date, sp_indy, lp_indy, gov_indy
        )
        day_rewards = _pkh_filter(day_rewards, pkh)
        sum_table = summary.get_summary(day_rewards)

    _output(sum_table)


@rewards.command(name="volatility")
@click.argument("iasset", type=click.STRING)
@click.argument("date", type=click.DateTime(formats=["%Y-%m-%d"]))
def volatility_command(iasset: str, date: datetime.datetime):
    """Print the volatility number for a given IASSET and DATE.

    IASSET: Single iAsset symbol, e.g. 'iUSD' or 'iBTC' or 'iETH', case insensitive.

    DATE: UTC day (of the snapshot) to calculate volatility for, e.g. '2022-11-25'
    """
    _load_polygon_api_key_or_fail(date, force=True)
    click.echo(str(volatility.get_volatility(iasset, date.date())))


def _to_df(rewards: list[IndividualReward]) -> pd.DataFrame:
    return pd.DataFrame(map(lambda x: x.as_dict(), rewards))


def _output(
    rewards: list[IndividualReward] | pd.DataFrame,
    outfile: Optional[str] = None,
):
    if isinstance(rewards, pd.DataFrame):
        df = rewards
    else:
        df = _to_df(rewards)
        if not outfile and not df.empty:
            df.Amount /= 1e6

    if df.empty:
        click.echo("No rewards.", err=True)
    else:
        if outfile:
            df.to_csv(outfile, index=False, lineterminator="\n", encoding="utf-8")
        else:
            click.echo(df.to_string(index=False))


def _pkh_filter(
    rewards: list[IndividualReward], pkh_starts: Optional[tuple[str]]
) -> list[IndividualReward]:
    if not pkh_starts:
        return rewards

    matching_rewards = []

    for pkh_start in pkh_starts:
        matching_pkhs = set(
            reward.pkh for reward in rewards if reward.pkh.startswith(pkh_start)
        )

        if len(matching_pkhs) > 1:
            raise click.BadParameter(
                f"PKH start '{pkh_start}' matches {len(matching_pkhs)} PKHs. "
                "Please use a longer string."
            )

        matching_rewards.extend([r for r in rewards if r.pkh.startswith(pkh_start)])

    return matching_rewards


def _load_polygon_api_key_or_fail(epoch_or_date: int | datetime.date, force=False):
    if not force:
        if isinstance(epoch_or_date, int):
            date = time_utils.get_epoch_first_snapshot_date(epoch_or_date)
        else:
            date = epoch_or_date

        if (
            date >= datetime.date(2023, 5, 26)
            and len(config.get_new_iassets(date)) == 0
        ):
            return

    polygon_api.load_api_key()
    if not polygon_api.POLYGON_API_KEY:
        click.echo(
            "Error: Please set POLYGON_API_KEY=... in the .env file or as an "
            "environment variable.",
            err=True,
        )
        sys.exit(1)


def _error_on_future(epoch_or_date: int | datetime.date):
    def get_snap_str(day: datetime.date) -> str:
        snap_time = time_utils.get_snapshot_time(day)
        return snap_time.strftime("%Y %B %d, %H:%M UTC")

    if isinstance(epoch_or_date, int):
        epoch = epoch_or_date
        epoch_end_day = time_utils.get_epoch_end_date(epoch)
        if time_utils.is_future_snapshot(epoch_end_day):
            raise click.BadArgumentUsage(
                f"Epoch's last snapshot must not be in the future. Epoch {epoch}'s "
                "last\nsnapshot is around:\n\n"
                f"{get_snap_str(epoch_end_day)}\n\n"
                "Plus up to 45 minutes until results appear on the API."
            )
    else:
        day = epoch_or_date
        if time_utils.is_future_snapshot(day):
            raise click.BadArgumentUsage(
                f"Snapshot for the day isn't done yet. It's around:\n\n"
                f"{get_snap_str(day)}\n\n"
                "Plus up to 45 minutes until results appear on the API."
            )