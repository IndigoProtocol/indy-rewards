import datetime

# Date of the "0th" epoch.
_ref_date = datetime.date(2017, 9, 23)


def get_snapshot_time(day: datetime.date) -> datetime.datetime:
    dt = datetime.datetime.combine(day, datetime.time(hour=21, minute=45))
    return dt.replace(tzinfo=datetime.timezone.utc)


def get_snapshot_unix_time(day: datetime.date) -> float:
    return get_snapshot_time(day).timestamp()


def date_to_epoch(date: datetime.date) -> int:
    """Get the epoch that 'date' is in.

    For epoch transition dates, it returns the epoch before the
    transition.
    """
    days_diff = (date - _ref_date).days - 1
    epoch = days_diff // 5
    return epoch


def get_epoch_end_date(epoch: int) -> datetime.date:
    """Get UTC date of the epoch's last block."""
    days_from_ref = (epoch + 1) * 5
    return _ref_date + datetime.timedelta(days=days_from_ref)


def get_epoch_first_snapshot_date(epoch: int) -> datetime.date:
    """Get first indy snapshot day for an epoch."""
    return get_epoch_end_date(epoch) - datetime.timedelta(days=4)


def get_epoch_snapshot_dates(epoch: int) -> list[datetime.date]:
    """
    Example:
        >>> get_snapshot_days(401)
        [datetime.date(2023, 3, 22),
         datetime.date(2023, 3, 23),
         datetime.date(2023, 3, 24),
         datetime.date(2023, 3, 25),
         datetime.date(2023, 3, 26)]
    """
    end = get_epoch_end_date(epoch)
    return [end - datetime.timedelta(days=x) for x in range(4, -1, -1)]


def get_sundae_import_period(date: datetime.date) -> int:
    return date_to_epoch(date) + 1


def get_reward_unlock_time(day: datetime.date) -> datetime.datetime:
    epoch = date_to_epoch(day)
    epoch_end_time = get_snapshot_time(get_epoch_end_date(epoch))
    unlock_time = epoch_end_time + datetime.timedelta(hours=1, minutes=15)
    return unlock_time


def get_reward_expiration(day: datetime.date) -> datetime.datetime:
    """Returns the reward expiration time for a reward day.

    Args:
        day: Day on which the reward was earned.

    Returns:
        Time after which the reward is no longer claimable.

    Examples:
        >>> get_reward_expiration(date(2023, 3, 23))
        datetime(2023, 6, 24, 21, 45)
        >>> get_reward_expiration(date(2023, 5, 5))
        datetime(2023, 8, 3, 21, 45)
        >>> get_reward_expiration(date(2023, 5, 6))
        datetime(2023, 8, 8, 21, 45)
        >>> get_reward_expiration(date(2023, 5, 10))
        datetime(2023, 8, 8, 21, 45)
    """
    day = get_epoch_end_date(date_to_epoch(day)) + datetime.timedelta(days=90)
    return datetime.datetime.combine(day, datetime.time(21, 45))


def is_future_snapshot(date: datetime.date) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc)
    return get_snapshot_time(date) > now
