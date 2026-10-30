"""UK-local time rules (R1, R5) on UTC timestamps.

All inputs and outputs are UTC-aware unless a name says "local". Wall-clock times
(cutoffs, delivery days) are always built as naive Europe/London datetimes and then
localised, so clock-change days get the right UTC offset. Adding hours to a UTC
midnight would be one hour off on those days.
"""

from datetime import date, timedelta

import pandas as pd

UK = "Europe/London"


def delivery_date(start_utc: pd.Series) -> pd.Series:
    """R5: the Europe/London calendar date of each period start (Series of datetime.date)."""
    return start_utc.dt.tz_convert(UK).dt.date


def local_midnight_utc(days: pd.Series) -> pd.Series:
    """UTC instant of 00:00 Europe/London on each date (Series of datetime.date)."""
    return pd.to_datetime(days).dt.tz_localize(UK).dt.tz_convert("UTC")


def decision_cutoff(day: date, cutoff_hhmm: str) -> pd.Timestamp:
    """R1: (day - 1) at cutoff_hhmm Europe/London, as a UTC Timestamp.

    E.g. delivery 2 Jan, "09:20" -> 2026-01-01 09:20 UTC (GMT). Delivery 30 Mar,
    "09:20" -> 2026-03-29 08:20 UTC, because clocks went forward that morning (BST).
    """
    naive = pd.Timestamp(f"{day - timedelta(days=1)} {cutoff_hhmm}")
    return naive.tz_localize(UK).tz_convert("UTC")


def decision_cutoffs(start_utc: pd.Series, cutoff_hhmm: str) -> pd.Series:
    """Vectorised decision_cutoff: the D-1 cutoff (UTC) for each period start."""
    hh, mm = (int(x) for x in cutoff_hhmm.split(":"))
    day_before = pd.to_datetime(delivery_date(start_utc)) - pd.Timedelta(days=1)
    naive = day_before + pd.Timedelta(hours=hh, minutes=mm)
    return naive.dt.tz_localize(UK).dt.tz_convert("UTC")


def settlement_period(start_utc: pd.Series) -> pd.Series:
    """GB settlement period: elapsed minutes since UK local midnight // 30 + 1.

    Uses real elapsed time, so a spring-forward day ends at SP 46 and an
    autumn day at SP 50 (48 otherwise).
    """
    midnight = local_midnight_utc(delivery_date(start_utc))
    return ((start_utc - midnight).dt.total_seconds() // 1800 + 1).astype(int)


def delivery_days(first: date, last: date) -> list[date]:
    """R4: every delivery date from first to last, inclusive."""
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
