"""Pydantic response models: the API contract. frontend/src/api/types.ts mirrors these."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
