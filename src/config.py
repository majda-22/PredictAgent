from __future__ import annotations

import os
from pathlib import Path


_LOADED = False


def load_env(path: str | Path = ".env", *, override: bool = False) -> None:
    """Load simple KEY=VALUE pairs from a local .env file."""
    global _LOADED
    if _LOADED:
        return

    env_path = Path(path)
    if not env_path.is_absolute():
        env_path = _project_root() / env_path
    if not env_path.exists():
        _LOADED = True
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _clean_value(value.strip())
        if key and (override or key not in os.environ):
            os.environ[key] = value

    _LOADED = True


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
