from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_env: str
    cors_allow_origins: list[str]
    cors_allow_credentials: bool
    http_timeout_s: float
    http_retries: int
    http_retry_backoff_s: float
    usda_api_key: str | None
    meal_calorie_model_path: str | None
    tesseract_cmd: str | None
    tesseract_lang: str


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_settings() -> Settings:
    # Loads from backend/.env if present (not committed) or environment.
    # IMPORTANT: We may run the server from the repo root, so explicitly point to backend/.env.
    backend_root = Path(__file__).resolve().parents[1]
    # Use override=True so a stale/empty environment var doesn't block the local backend/.env value.
    load_dotenv(dotenv_path=backend_root / ".env", override=True)
    # Also allow a repo-root .env (optional) without overriding already-set vars.
    load_dotenv(override=False)
    app_env = (os.getenv("APP_ENV") or "dev").strip().lower()
    cors_raw = os.getenv("CORS_ALLOW_ORIGINS") or ("*" if app_env == "dev" else "")
    cors_allow_origins = [x.strip() for x in cors_raw.split(",") if x.strip()]
    cors_allow_credentials = _parse_bool(os.getenv("CORS_ALLOW_CREDENTIALS"), default=(app_env == "dev"))
    return Settings(
        app_env=app_env,
        cors_allow_origins=cors_allow_origins,
        cors_allow_credentials=cors_allow_credentials,
        http_timeout_s=_parse_float(os.getenv("HTTP_TIMEOUT_S"), default=15.0),
        http_retries=_parse_int(os.getenv("HTTP_RETRIES"), default=2),
        http_retry_backoff_s=_parse_float(os.getenv("HTTP_RETRY_BACKOFF_S"), default=0.4),
        usda_api_key=os.getenv("USDA_API_KEY") or None,
        meal_calorie_model_path=os.getenv("MEAL_CALORIE_MODEL_PATH") or None,
        tesseract_cmd=os.getenv("TESSERACT_CMD") or None,
        tesseract_lang=os.getenv("TESSERACT_LANG") or "eng",
    )


