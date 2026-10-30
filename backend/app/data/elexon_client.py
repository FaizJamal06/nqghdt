"""Thin client for the two Elexon BMRS stream endpoints we use (FUELHH, WINDFOR).

Fetches in one-day chunks with retry + exponential backoff (PRD §4, §10). No API key.
Reused by the offline ingest CLI now and by the optional live mode later.
"""

import logging
import time
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
FUELHH_PATH = "/datasets/FUELHH/stream"
WINDFOR_PATH = "/datasets/WINDFOR/stream"
RETRY_STATUS = {429, 500, 502, 503, 504}

log = logging.getLogger(__name__)


class FuelhhRow(BaseModel):
    """One half-hour of actual generation for one fuel type. generation is average MW."""

    publishTime: datetime
    startTime: datetime
    settlementDate: date
    settlementPeriod: int
    fuelType: str
    # Nullable on purpose: loaders.py drops and *counts* nulls (R11), so they must survive ingest.
    generation: float | None


class WindforRow(BaseModel):
    """One forecast value: the publish it came from, the hour it targets, MW."""

    publishTime: datetime
    startTime: datetime
    generation: float | None


def validate_rows[M: BaseModel](raw: list[dict[str, Any]], model: type[M]) -> tuple[list[M], int]:
    """Validate raw JSON rows. Returns (valid rows, number skipped as malformed).

    Malformed rows are logged and skipped rather than failing the whole fetch, so one
    bad record can't block the snapshot; the count goes into manifest.json.
    """
    valid: list[M] = []
    bad = 0
    for row in raw:
        try:
            valid.append(model.model_validate(row))
        except ValidationError as exc:
            bad += 1
            log.warning("skipping malformed %s row: %s", model.__name__, exc.errors()[0])
    return valid, bad


class ElexonClient:
    """HTTP access to Elexon with retries. ``sleep`` is injectable so tests run instantly."""

    def __init__(
        self,
        http: httpx.Client | None = None,
        *,
        max_retries: int = 5,
        backoff_s: float = 1.0,
        pause_s: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=60)
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.pause_s = pause_s  # politeness gap between successful calls
        self.sleep = sleep

    def get_stream(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """GET one stream endpoint, retrying 429/5xx and network errors.

        Wait = Retry-After if the server sends it, else backoff_s * 2**attempt
        (1, 2, 4, 8, 16 s). Raises after max_retries so a broken fetch fails loudly
        instead of writing a silently incomplete snapshot.
        """
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise
                log.warning("network error %s on %s, retrying", exc, path)
                self.sleep(self.backoff_s * 2**attempt)
                continue
            if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                wait = float(resp.headers.get("Retry-After", self.backoff_s * 2**attempt))
                log.warning(
                    "HTTP %s on %s %s, retry in %.1fs", resp.status_code, path, params, wait
                )
                self.sleep(wait)
                continue
            resp.raise_for_status()
            self.sleep(self.pause_s)
            data: list[dict[str, Any]] = resp.json()
            return data
        raise AssertionError("unreachable")  # loop always returns or raises

    def fetch_fuelhh_wind(self, first: date, last: date) -> Iterator[list[dict[str, Any]]]:
        """Yield FUELHH WIND rows one settlement date (UK) at a time, first..last inclusive."""
        day = first
        while day <= last:
            d = day.isoformat()
            yield self.get_stream(
                FUELHH_PATH, {"settlementDateFrom": d, "settlementDateTo": d, "fuelType": "WIND"}
            )
            day += timedelta(days=1)

    def fetch_windfor(self, start: datetime, end: datetime) -> Iterator[list[dict[str, Any]]]:
        """Yield WINDFOR rows for publish times in [start, end) UTC, one day per request.

        Both API bounds are inclusive, so each chunk ends 1 s before the next starts;
        otherwise a publish exactly at midnight would be fetched twice.
        """
        chunk = start
        while chunk < end:
            chunk_end = min(chunk + timedelta(days=1), end) - timedelta(seconds=1)
            yield self.get_stream(
                WINDFOR_PATH,
                {
                    "publishDateTimeFrom": chunk.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "publishDateTimeTo": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            chunk += timedelta(days=1)
