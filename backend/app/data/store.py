"""DataStore: the snapshot loaded once, plus cached derived frames per selection mode.

A mode key is ("cutoff", "09:20") or ("horizon", 24.0). Everything downstream of a key
(selection, scored frame, fitted correction + bands) is computed once and kept in a
bounded LRU cache, so warm API requests only slice and serialise (PRD §8: < 300 ms).
Cached frames are shared: callers must not modify them in place.
"""

from dataclasses import dataclass
from datetime import date
from functools import cache, lru_cache

import pandas as pd

from app.config import Settings
from app.core import bands, correction, metrics, selection
from app.core.alignment import score, train_test_split
from app.core.timeutils import UK, delivery_date, settlement_period
from app.data.loaders import Snapshot

Key = tuple[str, str | float]


@dataclass(frozen=True)
class Fitted:
    """Correction + band model fitted on the leak-free train rows of one mode (#38)."""

    correction: correction.Correction
    model: bands.BandModel
    train: pd.DataFrame  # scored + centre_mw, resid_mw
    test: pd.DataFrame


class DataStore:
    """Read-only access to cleaned data and cached analytics. One instance per app."""

    def __init__(self, snap: Snapshot, settings: Settings) -> None:
        self.snap, self.s = snap, settings
        self.publish_times = pd.Series(snap.forecasts["publishTime"].unique())
        self.selected = lru_cache(maxsize=64)(self._selected)
        self.scored = lru_cache(maxsize=64)(self._scored)
        self.fitted = lru_cache(maxsize=64)(self._fitted)
        self.calibration = lru_cache(maxsize=64)(self._calibration)

    @staticmethod
    def key(mode: str, cutoff: str, horizon_h: float) -> Key:
        """Normalise request params to a cache key (horizon only matters in horizon mode)."""
        return ("cutoff", cutoff) if mode == "cutoff" else ("horizon", float(horizon_h))

    def _selected(self, key: Key) -> pd.DataFrame:
        """Selected forecast per hour (R2/R8) with previous publish, revision, delivery_date."""
        f = self.snap.forecasts
        mode, value = key
        if mode == "cutoff":
            sel = selection.select_at_cutoff(f, str(value))
        else:
            sel = selection.select_at_horizon(f, float(value))
        sel = selection.previous_publish(f, sel)
        sel["delivery_date"] = delivery_date(sel["startTime"])
        in_window = sel["delivery_date"].between(self.s.delivery_first, self.s.delivery_last)
        return sel[in_window].reset_index(drop=True)

    def _scored(self, key: Key) -> tuple[pd.DataFrame, dict[str, int]]:
        """Scored frame + coverage for the delivery window (core/alignment.py)."""
        s, snap = self.s, self.snap
        return score(
            self.selected(key), snap.actuals, snap.resolution_min, s.delivery_first, s.delivery_last
        )

    def _fitted(self, key: Key) -> Fitted:
        """Fit the configured correction and the band cells on train rows only."""
        s = self.s
        train, test = train_test_split(self.scored(key)[0], s.band_train_end, s.train_known_before)
        corr = correction.fit(train, s.correction)
        train, test = correction.with_centre(train, corr), correction.with_centre(test, corr)
        model = bands.fit_bands(train, s.band_horizon_buckets, s.band_level_bins, s.band_min_cell)
        return Fitted(corr, model, train, test)

    def _calibration(self, key: Key) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Band coverage (with the by-day bootstrap) and every correction candidate scored
        on test: (levels, compare). Slow (~0.5 s), so cached like the fit."""
        fit = self.fitted(key)
        return bands.calibration(fit.model, fit.train, fit.test), correction.compare(
            fit.train, fit.test
        )

    def day_frame(self, key: Key, day: date) -> pd.DataFrame:
        """One delivery day's selected rows with centre_mw, local labels and actuals (if any).

        Built from the selection, not the scored frame, so an hour with a forecast but no
        actual still appears (actual_mw NaN).
        """
        sel = self.selected(key)
        frame = sel[sel["delivery_date"] == day].copy()
        frame["centre_mw"] = correction.apply(self.fitted(key).correction, frame)
        local = frame["startTime"].dt.tz_convert(UK)
        frame["local_time"] = local.dt.strftime("%H:%M")
        frame["hour_uk"] = local.dt.hour
        frame["sp"] = settlement_period(frame["startTime"])
        frame["dt_h"] = self.snap.resolution_min / 60
        actual = self.scored(key)[0][["startTime", "actual_mw", "error_mw"]]
        return frame.merge(actual, on="startTime", how="left").reset_index(drop=True)

    @cache  # noqa: B019 - one store per app, lives as long as the process
    def lead_time(self) -> pd.DataFrame:
        """Error vs lead time (DECISIONS #25): n, MAE, bias in horizon mode, h = 1..max."""
        rows = []
        for h in range(1, int(self.s.horizon_max_h) + 1):
            sm = metrics.summary(self.scored(("horizon", float(h)))[0])
            rows.append({"horizon_h": h, "n": sm["n"], "mae": sm["mae"], "bias": sm["bias"]})
        return pd.DataFrame(rows)

    @cache  # noqa: B019
    def value_of_waiting(self) -> pd.DataFrame:
        """MAE/bias at each cutoff preset on the same periods (DECISIONS #26)."""
        frames = {c: self.scored(("cutoff", c))[0] for c in self.s.cutoff_presets}
        return metrics.on_common_periods(frames)

    def warm(self) -> None:
        """Precompute the default mode and the mode-independent tables at startup."""
        self.calibration(("cutoff", self.s.cutoff_default))
        self.lead_time()
        self.value_of_waiting()
