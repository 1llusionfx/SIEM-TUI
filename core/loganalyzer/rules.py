from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, PositiveInt


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    window_seconds: PositiveInt
    severity: Literal["low", "medium", "high"]


class LoginRule(Rule):
    threshold: PositiveInt


class ScanRule(Rule):
    missing_threshold: PositiveInt
    paths_threshold: PositiveInt


class Rules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brute_force: LoginRule
    scan: ScanRule
    credential_stuffing: LoginRule


def load_rules(path: Path) -> Rules:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {path}: {error}") from error
    return Rules.model_validate(data)
