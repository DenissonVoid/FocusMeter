from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import Config, save_config

RULE_WORK = "work"
RULE_DISTRACTING = "distracting"
RULE_EXCLUDED = "excluded"
RULE_NONE = "none"

RULE_LABELS = {
    RULE_WORK: "Рабочее",
    RULE_DISTRACTING: "Отвлекающее",
    RULE_EXCLUDED: "Исключено",
    RULE_NONE: "Без правила",
}


def normalize_process_name(value: str) -> str:
    return (value or "").strip().lower()


def _parse_timestamp(value: str) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


@dataclass
class AppHistoryEntry:
    process_name: str
    window_title: str = ""
    exe_path: str = ""
    last_seen_utc: str = ""
    seen_count: int = 0


@dataclass
class AppRulesState:
    work_apps: set[str] = field(default_factory=set)
    distracting_apps: set[str] = field(default_factory=set)
    excluded_apps: set[str] = field(default_factory=set)
    favorites: set[str] = field(default_factory=set)
    history: dict[str, AppHistoryEntry] = field(default_factory=dict)


class AppRulesRepository:
    def __init__(self, config: Config):
        self.config = config
        self.path = Path(config.app_rules_path)
        self.state = self._load_state()
        self.apply_to_config(persist=False)

    def _legacy_state(self) -> AppRulesState:
        return AppRulesState(
            work_apps=set(self.config.work_apps),
            distracting_apps=set(self.config.distracting_apps),
        )

    def _load_state(self) -> AppRulesState:
        legacy = self._legacy_state()
        if not self.path.exists():
            self._ensure_parent_dir()
            self.state = legacy
            self.save()
            return legacy

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self.state = legacy
            self.save()
            return legacy

        rules = raw.get("rules", {})
        history_raw = raw.get("history", {})
        favorites_raw = raw.get("favorites", [])

        state = AppRulesState(
            work_apps={normalize_process_name(item) for item in rules.get("work", []) if item},
            distracting_apps={
                normalize_process_name(item)
                for item in rules.get("distracting", [])
                if item
            },
            excluded_apps={
                normalize_process_name(item)
                for item in rules.get("excluded", [])
                if item
            },
            favorites={
                normalize_process_name(item) for item in favorites_raw if item
            },
        )

        for key, payload in history_raw.items():
            process_name = normalize_process_name(payload.get("process_name") or key)
            if not process_name:
                continue
            state.history[process_name] = AppHistoryEntry(
                process_name=process_name,
                window_title=(payload.get("window_title") or "").strip(),
                exe_path=(payload.get("exe_path") or "").strip(),
                last_seen_utc=(payload.get("last_seen_utc") or "").strip(),
                seen_count=int(payload.get("seen_count", 0)),
            )

        if legacy.work_apps and not state.work_apps:
            state.work_apps |= legacy.work_apps
        if legacy.distracting_apps and not state.distracting_apps:
            state.distracting_apps |= legacy.distracting_apps

        return state

    def _ensure_parent_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def reload(self) -> AppRulesState:
        self.state = self._load_state()
        self.apply_to_config(persist=False)
        return self.state

    def save(self) -> None:
        self._ensure_parent_dir()
        payload = {
            "version": 1,
            "rules": {
                "work": sorted(self.state.work_apps),
                "distracting": sorted(self.state.distracting_apps),
                "excluded": sorted(self.state.excluded_apps),
            },
            "favorites": sorted(self.state.favorites),
            "history": {
                key: {
                    "process_name": entry.process_name,
                    "window_title": entry.window_title,
                    "exe_path": entry.exe_path,
                    "last_seen_utc": entry.last_seen_utc,
                    "seen_count": entry.seen_count,
                }
                for key, entry in sorted(self.state.history.items())
            },
        }
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def apply_to_config(self, persist: bool = True) -> None:
        self.config.work_apps = sorted(self.state.work_apps)
        self.config.distracting_apps = sorted(self.state.distracting_apps)
        if persist:
            save_config(self.config)

    def get_rule(self, process_name: str) -> str:
        key = normalize_process_name(process_name)
        if not key:
            return RULE_NONE
        if key in self.state.work_apps:
            return RULE_WORK
        if key in self.state.distracting_apps:
            return RULE_DISTRACTING
        if key in self.state.excluded_apps:
            return RULE_EXCLUDED
        return RULE_NONE

    def set_rule(self, process_name: str, rule: str) -> None:
        key = normalize_process_name(process_name)
        if not key:
            return

        self.state.work_apps.discard(key)
        self.state.distracting_apps.discard(key)
        self.state.excluded_apps.discard(key)

        if rule == RULE_WORK:
            self.state.work_apps.add(key)
        elif rule == RULE_DISTRACTING:
            self.state.distracting_apps.add(key)
        elif rule == RULE_EXCLUDED:
            self.state.excluded_apps.add(key)

        self.save()
        self.apply_to_config(persist=True)

    def toggle_favorite(self, process_name: str) -> bool:
        key = normalize_process_name(process_name)
        if not key:
            return False
        if key in self.state.favorites:
            self.state.favorites.remove(key)
            result = False
        else:
            self.state.favorites.add(key)
            result = True
        self.save()
        return result

    def record_observation(
        self,
        process_name: str,
        window_title: str = "",
        exe_path: str = "",
        observed_at: datetime | None = None,
    ) -> bool:
        key = normalize_process_name(process_name)
        if not key:
            return False

        when = observed_at or datetime.utcnow()
        entry = self.state.history.get(key)
        if entry is None:
            entry = AppHistoryEntry(process_name=key)
            self.state.history[key] = entry

        entry.window_title = (window_title or entry.window_title).strip()
        entry.exe_path = (exe_path or entry.exe_path).strip()
        entry.last_seen_utc = when.isoformat()
        entry.seen_count += 1
        self.save()
        return True

    def get_recent_apps(
        self,
        limit: int = 100,
        favorites_only: bool = False,
    ) -> list[AppHistoryEntry]:
        items = list(self.state.history.values())
        if favorites_only:
            items = [item for item in items if item.process_name in self.state.favorites]

        def sort_key(item: AppHistoryEntry) -> tuple[bool, str, str]:
            timestamp = _parse_timestamp(item.last_seen_utc)
            sortable = timestamp.isoformat() if timestamp != datetime.min else ""
            return (
                item.process_name in self.state.favorites,
                sortable,
                item.process_name,
            )

        items.sort(
            key=sort_key,
            reverse=True,
        )
        return items[:limit]

    def find_conflicts(self) -> list[str]:
        return sorted(self.state.work_apps & self.state.distracting_apps)
