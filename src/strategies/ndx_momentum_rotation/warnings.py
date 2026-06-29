"""Warnings and validity classification for ndx_momentum_rotation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BacktestValidity(str, Enum):
    RESEARCH_GRADE = "RESEARCH_GRADE"
    INDICATIVE_ONLY = "INDICATIVE_ONLY"


@dataclass(frozen=True)
class StrategyWarning:
    code: str
    message: str


def classify_validity(survivorship_mode: str) -> BacktestValidity:
    if survivorship_mode == "current_members":
        return BacktestValidity.INDICATIVE_ONLY
    return BacktestValidity.RESEARCH_GRADE
