import datetime
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from . import time_utils


class IAsset(Enum):
    """Enum representing an iAsset.

    Examples:
        >>> IAsset.from_str('iusd')
        IAsset(iUSD)
        >>> IAsset.from_str('IUsD')
        IAsset(iUSD)
    """

    iUSD = auto()
    iBTC = auto()
    iETH = auto()

    @classmethod
    def from_str(cls, name: str):
        for member in cls:
            if member.name.lower() == name.lower():
                return member
        raise ValueError(f"Invalid IAsset: {name}")

    def __repr__(self):
        return f"IAsset({self.name})"


class Dex(Enum):
    Minswap = auto()
    MuesliSwap = auto()
    WingRiders = auto()

    @classmethod
    def from_str(cls, name: str):
        for member in cls:
            if member.name.lower() == name.lower():
                return member
        raise ValueError(f"No Dex matching '{name}'")

    def __repr__(self):
        return f"Dex({self.name})"


@dataclass(frozen=True, eq=True)
class LiquidityPool:
    dex: Dex
    iasset: IAsset
    other_asset_name: str
    lp_token_id: str


@dataclass(frozen=True, eq=True)
class LiquidityPoolStatus:
    lp: LiquidityPool
    iasset_balance: float
    lp_token_circ_supply: Optional[int]
    lp_token_staked: Optional[int]
    timestamp: datetime.datetime


@dataclass(frozen=True, eq=True)
class StabilityPool:
    iasset: IAsset


@dataclass(frozen=True, eq=True)
class StabilityPoolStatus:
    sp: StabilityPool
    iasset_balance: float
    timestamp: datetime.datetime


@dataclass(frozen=True, eq=True)
class BaseReward:
    indy: float
    day: datetime.date

    def get_indy_lovelaces(self) -> int:
        return round(self.indy * 1_000_000)


@dataclass(frozen=True, eq=True)
class IAssetReward(BaseReward):
    iasset: IAsset


@dataclass(frozen=True, eq=True)
class LiquidityPoolReward(BaseReward):
    lp: LiquidityPool


@dataclass(frozen=True, eq=True)
class IndividualReward(BaseReward):
    pkh: str
    expiration: datetime.date
    description: str

    def as_dict(self):
        return {
            "Period": time_utils.get_sundae_import_period(self.day),
            "Address": self.pkh,
            "Purpose": self.description,
            "Date": self.day,
            "Amount": self.get_indy_lovelaces(),
            "Expiration": self.expiration.strftime("%Y-%m-%d %H:%M"),
            "AvailableAt": time_utils.get_reward_unlock_time(self.day).strftime(
                "%Y-%m-%d %H:%M"
            ),
        }
