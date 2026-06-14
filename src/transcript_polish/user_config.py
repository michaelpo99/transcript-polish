from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

SUPPORTED_MODES = {"standard", "quality"}


class UserConfigError(ValueError):
    pass


def get_user_config_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / "transcript-polish" / "config.toml"
    return Path.home() / ".config" / "transcript-polish" / "config.toml"


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            payload = tomllib.load(stream)
    except Exception as exc:
        raise UserConfigError(f"使用者設定檔格式錯誤：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UserConfigError(f"使用者設定檔必須是 TOML table：{path}")
    return payload


def load_user_mode(path: Path | None = None) -> str | None:
    config_path = path or get_user_config_path()
    if not config_path.exists():
        return None
    if not config_path.is_file():
        raise UserConfigError(f"使用者設定檔不是一般檔案：{config_path}")

    payload = _load_toml(config_path)
    mode = payload.get("mode")
    if mode is None:
        return None
    if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
        raise UserConfigError(
            f"使用者設定檔的 mode 必須是 standard 或 quality：{config_path}"
        )
    return mode


def write_user_mode(mode: str, path: Path | None = None) -> Path:
    if mode not in SUPPORTED_MODES:
        raise UserConfigError(f"不支援的 mode：{mode}")

    config_path = path or get_user_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        if not config_path.is_file():
            raise UserConfigError(f"使用者設定檔不是一般檔案：{config_path}")
        _load_toml(config_path)
        original = config_path.read_text(encoding="utf-8")
    else:
        original = ""

    mode_line = f'mode = "{mode}"'
    lines = original.splitlines()
    mode_pattern = re.compile(r"^\s*mode\s*=")
    table_pattern = re.compile(r"^\s*\[")

    replaced = False
    updated: list[str] = []
    for line in lines:
        if not replaced and mode_pattern.match(line):
            updated.append(mode_line)
            replaced = True
        else:
            updated.append(line)

    if not replaced:
        insert_at = next(
            (index for index, line in enumerate(updated) if table_pattern.match(line)),
            len(updated),
        )
        prefix = [mode_line]
        if updated and insert_at == 0:
            prefix.append("")
        updated[insert_at:insert_at] = prefix

    text = "\n".join(updated).rstrip() + "\n"
    config_path.write_text(text, encoding="utf-8")
    return config_path
