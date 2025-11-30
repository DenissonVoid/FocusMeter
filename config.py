# config.py

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
import json
import sys

# -------------------------------------------------
# БАЗОВЫЙ КАТАЛОГ ДЛЯ CONFIG.JSON И БД
# -------------------------------------------------
# - при запуске из .exe (PyInstaller onefile) — каталог рядом с exe
# - при запуске из исходников — папка, где лежит config.py

if getattr(sys, "frozen", False):
    # режим собранного exe
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # обычный Python-скрипт
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH_DEFAULT = BASE_DIR / "focusmeter.db"


@dataclass
class Config:
    # базовые интервалы (по умолчанию — Помодоро 25/5)
    poll_interval_seconds: int = 1
    idle_threshold_seconds: int = 10
    idle_warning_minutes: int = 10
    break_warning_minutes: int = 25

    # уведомления
    notify_on_idle: bool = True
    notify_on_break: bool = True

    # списки приложений
    work_apps: list[str] = field(default_factory=list)
    distracting_apps: list[str] = field(default_factory=list)

    # путь к БД
    db_path: str = str(DB_PATH_DEFAULT)

    # тема интерфейса
    # "system" — системная
    # "light"  — светлая Fusion
    # "dark"   — тёмная Fusion
    theme: str = "dark"


def load_config() -> Config:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        return Config(
            poll_interval_seconds=raw.get("poll_interval_seconds", 1),
            idle_threshold_seconds=raw.get("idle_threshold_seconds", 10),
            idle_warning_minutes=raw.get("idle_warning_minutes", 10),
            break_warning_minutes=raw.get("break_warning_minutes", 25),
            notify_on_idle=raw.get("notify_on_idle", True),
            notify_on_break=raw.get("notify_on_break", True),
            work_apps=list(raw.get("work_apps", [])),
            distracting_apps=list(raw.get("distracting_apps", [])),
            db_path=raw.get("db_path", str(DB_PATH_DEFAULT)),
            theme=raw.get("theme", "dark"),
        )

    # если конфиг ещё не создан — создаём с настройками по умолчанию
    cfg = Config()
    save_config(cfg)
    return cfg


def save_config(cfg: Config) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
