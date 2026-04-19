from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH_DEFAULT = BASE_DIR / "focusmeter.db"
APP_RULES_PATH_DEFAULT = BASE_DIR / "app_rules.json"


def _normalize_app_names(values: list[str]) -> list[str]:
    normalized = []
    seen: set[str] = set()
    for value in values:
        item = (value or "").strip().lower()
        if item and item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


@dataclass
class Config:
    poll_interval_seconds: int = 1
    idle_threshold_seconds: int = 10
    idle_warning_minutes: int = 10
    break_warning_minutes: int = 25

    notify_on_idle: bool = True
    notify_on_break: bool = True

    work_apps: list[str] = field(default_factory=list)
    distracting_apps: list[str] = field(default_factory=list)

    db_path: str = str(DB_PATH_DEFAULT)
    theme: str = "dark"

    widget_always_on_top: bool = True
    widget_compact_mode: bool = False
    app_rules_path: str = str(APP_RULES_PATH_DEFAULT)


def load_config() -> Config:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        cfg = Config(
            poll_interval_seconds=int(raw.get("poll_interval_seconds", 1)),
            idle_threshold_seconds=int(raw.get("idle_threshold_seconds", 10)),
            idle_warning_minutes=int(raw.get("idle_warning_minutes", 10)),
            break_warning_minutes=int(raw.get("break_warning_minutes", 25)),
            notify_on_idle=bool(raw.get("notify_on_idle", True)),
            notify_on_break=bool(raw.get("notify_on_break", True)),
            work_apps=list(raw.get("work_apps", [])),
            distracting_apps=list(raw.get("distracting_apps", [])),
            db_path=raw.get("db_path", str(DB_PATH_DEFAULT)),
            theme=raw.get("theme", "dark"),
            widget_always_on_top=bool(raw.get("widget_always_on_top", True)),
            widget_compact_mode=bool(raw.get("widget_compact_mode", False)),
            app_rules_path=raw.get("app_rules_path", str(APP_RULES_PATH_DEFAULT)),
        )
        cfg.work_apps = _normalize_app_names(cfg.work_apps)
        cfg.distracting_apps = _normalize_app_names(cfg.distracting_apps)
        return cfg

    cfg = Config()
    save_config(cfg)
    return cfg


def save_config(cfg: Config) -> None:
    cfg.work_apps = _normalize_app_names(cfg.work_apps)
    cfg.distracting_apps = _normalize_app_names(cfg.distracting_apps)

    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(asdict(cfg), handle, ensure_ascii=False, indent=2)
