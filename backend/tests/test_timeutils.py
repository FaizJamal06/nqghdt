"""R1/R5 time rules, including the 2026 clock changes (29 Mar forward, 25 Oct back)."""

from datetime import date

import pandas as pd
import pytest

from app.core.timeutils import (
    decision_cutoff,
    decision_cutoffs,
    delivery_date,
    delivery_days,
    settlement_period,
)


@pytest.mark.parametrize(
    "day,expected",
    [
        (date(2026, 1, 2), "2026-01-01T09:20Z"),  # GMT: local = UTC
        (date(2026, 3, 29), "2026-03-28T09:20Z"),  # D-1 still GMT
        (date(2026, 3, 30), "2026-03-29T08:20Z"),  # D-1 is BST after the 01:00 UTC change
        (date(2026, 10, 25), "2026-10-24T08:20Z"),  # D-1 still BST
        (date(2026, 10, 26), "2026-10-25T09:20Z"),  # D-1 back on GMT
    ],
)
def test_decision_cutoff_is_dst_correct(day: date, expected: str) -> None:
    assert decision_cutoff(day, "09:20") == pd.Timestamp(expected)


def test_vectorised_cutoffs_match_scalar() -> None:
    starts = pd.Series(pd.to_datetime(["2026-01-02T00:00Z", "2026-03-29T23:00Z"]))
    # 29 Mar 23:00 UTC is 30 Mar 00:00 BST -> delivery day 30 Mar -> cutoff 29 Mar 08:20 UTC
    assert decision_cutoffs(starts, "09:20").tolist() == [
        decision_cutoff(date(2026, 1, 2), "09:20"),
        decision_cutoff(date(2026, 3, 30), "09:20"),
    ]


def test_delivery_date_uses_uk_local_date() -> None:
    starts = pd.Series(pd.to_datetime(["2026-01-15T23:30Z", "2026-03-29T23:30Z"]))
    assert delivery_date(starts).tolist() == [date(2026, 1, 15), date(2026, 3, 30)]


def test_settlement_periods_on_normal_and_clock_change_days() -> None:
    starts = pd.Series(
        pd.to_datetime(
            [
                "2026-01-15T00:00Z",  # SP 1
                "2026-01-15T17:00Z",  # SP 35 (the worked example hour)
                "2026-03-29T22:30Z",  # 23:30 BST, last SP of a 46-period day
                "2026-10-25T23:30Z",  # 23:30 GMT, last SP of a 50-period day
            ]
        )
    )
    assert settlement_period(starts).tolist() == [1, 35, 46, 50]


def test_delivery_days_cover_the_window() -> None:
    days = delivery_days(date(2026, 1, 2), date(2026, 2, 1))
    assert (len(days), days[0], days[-1]) == (31, date(2026, 1, 2), date(2026, 2, 1))
