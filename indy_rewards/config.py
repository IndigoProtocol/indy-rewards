import datetime
from typing import Final

from .models import IAsset
from .time_utils import date_to_epoch

LP_EPOCH_INDY: Final[int] = 4795
GOV_EPOCH_INDY: Final[int] = 2398

IASSET_LAUNCH_DATES = {
    IAsset.iUSD: datetime.date(2022, 11, 21),  # Epoch 377's first day.
    IAsset.iBTC: datetime.date(2022, 11, 21),
    IAsset.iETH: datetime.date(2023, 1, 6),  # Epoch 386's second day.
}


def get_active_iassets(day: datetime.date) -> set[IAsset]:
    return set([x for x in IAsset if IASSET_LAUNCH_DATES[x] <= day])


def get_new_iassets(day: datetime.date) -> set[IAsset]:
    """Get iAssets that are less than 6 epochs old."""
    return set(
        [
            x
            for x in IAsset
            if x in get_active_iassets(day)
            and date_to_epoch(day) < date_to_epoch(IASSET_LAUNCH_DATES[x]) + 6
        ]
    )
