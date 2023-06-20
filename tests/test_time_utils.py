import datetime
from datetime import date

import pytest

from indy_rewards import time_utils

date_epochs = [
    (date(2022, 3, 30), 329),
    (date(2022, 4, 1), 330),
    (date(2022, 4, 4), 330),
    (date(2022, 4, 5), 330),
    (date(2022, 4, 6), 331),
    (date(2023, 3, 15), 399),
    (date(2023, 3, 16), 399),
    (date(2023, 3, 17), 400),
    (date(2023, 3, 18), 400),
    (date(2023, 3, 21), 400),
    (date(2023, 3, 22), 401),
    (date(2024, 2, 12), 466),
    (date(2024, 2, 14), 466),
    (date(2024, 2, 15), 467),
]


epoch_end_dates = [
    (331, date(2022, 4, 10)),
    (398, date(2023, 3, 11)),
    (399, date(2023, 3, 16)),
    (400, date(2023, 3, 21)),
    (401, date(2023, 3, 26)),
    (466, date(2024, 2, 14)),
    (467, date(2024, 2, 19)),
]


epoch_snapshot_days = [
    (
        378,
        [
            date(2022, 11, 27),
            date(2022, 11, 28),
            date(2022, 11, 29),
            date(2022, 11, 30),
            date(2022, 12, 1),
        ],
    ),
    (
        384,
        [
            date(2022, 12, 27),
            date(2022, 12, 28),
            date(2022, 12, 29),
            date(2022, 12, 30),
            date(2022, 12, 31),
        ],
    ),
    (
        415,
        [
            date(2023, 5, 31),
            date(2023, 6, 1),
            date(2023, 6, 2),
            date(2023, 6, 3),
            date(2023, 6, 4),
        ],
    ),
    (
        470,
        [
            date(2024, 3, 1),
            date(2024, 3, 2),
            date(2024, 3, 3),
            date(2024, 3, 4),
            date(2024, 3, 5),
        ],
    ),
]


@pytest.mark.parametrize("date,epoch", date_epochs)
def test_date_to_epoch(date, epoch):
    assert time_utils.date_to_epoch(date) == epoch


@pytest.mark.parametrize("epoch,date", epoch_end_dates)
def test_epoch_end_to_date(epoch, date):
    assert time_utils.get_epoch_end_date(epoch) == date


@pytest.mark.parametrize("epoch,expected_dates", epoch_snapshot_days)
def test_get_epoch_snapshot_dates(epoch, expected_dates):
    result = time_utils.get_epoch_snapshot_dates(epoch)
    assert result == expected_dates


@pytest.mark.parametrize(
    "day,expiration",
    [
        (date(2023, 3, 23), datetime.datetime(2023, 6, 24, 21, 45)),
        (date(2023, 5, 5), datetime.datetime(2023, 8, 3, 21, 45)),
        (date(2023, 5, 6), datetime.datetime(2023, 8, 8, 21, 45)),
        (date(2023, 5, 10), datetime.datetime(2023, 8, 8, 21, 45)),
    ],
)
def test_get_reward_expiration(day, expiration):
    assert time_utils.get_reward_expiration(day) == expiration
