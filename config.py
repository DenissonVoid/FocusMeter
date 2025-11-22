# config.py

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path


CONFIG_FILENAME = "config.json"


@dataclass
class Config:
    # раз в сколько секунд опрашивать активное окно и писать статистику
    poll_interval_seconds: int = 1

    # сколько секунд можно не трогать мышь/клавиатуру, но считаться, что пользователь еще "активен"
    idle_threshold_seconds: int = 60

    # через сколько минут бездействия напоминать, что пользователь неактивен
    idle_warning_minutes: int = 10

    # через сколько минут непрерывной работы напоминать, что пора отдохнуть
    break_warning_minutes: int = 50

    # списки имен процессов (exe / bin), которые считаются рабочими и отвлекающими
    work_apps: list[str] = field(default_factory=list)
    distracting_apps: list[str] = field(default_factory=list)

    # включать ли уведомления
    notify_on_idle: bool = True
    notify_on_break: bool = True

    # путь к базе данных
    db_path: str = "focusmeter.db"

    def __post_init__(self):
        # нормализуем имена приложений к нижнему регистру
        self.work_apps = [a.lower() for a in self.work_apps]
        self.distracting_apps = [a.lower() for a in self.distracting_apps]


def get_config_path() -> Path:
    # config.json лежит рядом с этим файлом
    return Path(__file__).resolve().parent / CONFIG_FILENAME


def load_config() -> Config:
    """
    Загружает настройки из config.json.
    Если файла нет — создаёт его с настройками по умолчанию.
    """
    path = get_config_path()

    if not path.exists():
        cfg = Config()
        # Пример значений по умолчанию (можешь потом поправить вручную)
        cfg.work_apps = ["code.exe", "pycharm64.exe", "excel.exe"]
        cfg.distracting_apps = ["chrome.exe", "discord.exe", "telegram.exe"]
        cfg.__post_init__()

        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, ensure_ascii=False, indent=4)

        print(
            f"[CONFIG] Создан {CONFIG_FILENAME} с настройками по умолчанию.\n"
            f"Отредактируй его или используй интерфейс для изменения."
        )
        return cfg

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    default_cfg = Config()
    default_dict = asdict(default_cfg)
    default_dict.update(data)

    cfg = Config(**default_dict)
    return cfg


def save_config(cfg: Config) -> None:
    """
    Сохраняет настройки в config.json.
    """
    cfg.__post_init__()  # ещё раз нормализуем списки приложений
    path = get_config_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=4)
    print("[CONFIG] Настройки сохранены в config.json")
