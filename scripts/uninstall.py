#!/usr/bin/env python3
"""Interactive uninstaller for transcript-polish."""

from __future__ import annotations

import argparse
import ast
import os
import shutil
import sys
from pathlib import Path
from typing import Any


class UninstallError(RuntimeError):
    pass


def ask_yes_no(question: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes", "是"}:
            return True
        if answer in {"n", "no", "否"}:
            return False
        print("請輸入 y 或 n。")


def parse_minimal_installer_section(path: Path) -> dict[str, Any]:
    """Fallback parser for the simple installer section used by this project."""
    result: dict[str, Any] = {}
    active = False
    pending_key = ""
    pending_value: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            if pending_key:
                result[pending_key] = ast.literal_eval(" ".join(pending_value))
                pending_key = ""
                pending_value = []
            active = line == "[tool.transcript-polish.installer]"
            continue
        if not active:
            continue
        if pending_key:
            pending_value.append(line)
            if line.endswith("]"):
                result[pending_key] = ast.literal_eval(" ".join(pending_value))
                pending_key = ""
                pending_value = []
            continue
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if value.startswith("[") and not value.endswith("]"):
            pending_key = key
            pending_value = [value]
        else:
            result[key] = ast.literal_eval(value)

    if pending_key:
        result[pending_key] = ast.literal_eval(" ".join(pending_value))
    return result


def load_installer_metadata(path: Path) -> dict[str, Any]:
    try:
        import tomllib  # type: ignore
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            print("注意：找不到 tomllib / tomli，使用內建的最小 TOML 解析器。")
            return parse_minimal_installer_section(path)

    with path.open("rb") as stream:
        data = tomllib.load(stream)
    return data.get("tool", {}).get("transcript-polish", {}).get("installer", {})


def expand_config_path(value: str, env_name: str) -> Path:
    selected = os.environ.get(env_name, value)
    return Path(selected).expanduser().resolve()


def wrapper_is_managed(wrapper: Path, command_name: str, venv_dir: Path) -> bool:
    if wrapper.is_symlink():
        try:
            return wrapper.resolve() == (venv_dir / "bin" / command_name).resolve()
        except OSError:
            return False
    if not wrapper.is_file():
        return False
    try:
        text = wrapper.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return (
        "Managed by transcript-polish installer" in text
        or (
            "TRANSCRIPT_POLISH_VENV" in text
            and f'bin/{command_name}' in text
            and "exec" in text
        )
    )


def safe_to_remove_venv(venv_dir: Path, repo_root: Path) -> bool:
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo_root.resolve(),
        (Path.home() / ".venvs").resolve(),
    }
    return venv_dir.resolve() not in forbidden


def remove_path_block(bashrc: Path, bin_dir: Path, *, dry_run: bool) -> bool:
    if not bashrc.exists():
        return False

    marker = "# transcript-polish user commands"
    export_line = (
        'export PATH="$HOME/bin:$PATH"'
        if bin_dir == (Path.home() / "bin").resolve()
        else f'export PATH="{bin_dir}:$PATH"'
    )
    lines = bashrc.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    removed = False
    index = 0
    while index < len(lines):
        if (
            lines[index].strip() == marker
            and index + 1 < len(lines)
            and lines[index + 1].strip() == export_line
        ):
            removed = True
            if output and not output[-1].strip():
                output.pop()
            index += 2
            continue
        output.append(lines[index])
        index += 1

    if removed and not dry_run:
        bashrc.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    return removed


def directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def huggingface_hub_dir() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser().resolve()
    if os.environ.get("HF_HOME"):
        return (Path(os.environ["HF_HOME"]).expanduser() / "hub").resolve()
    return (Path.home() / ".cache" / "huggingface" / "hub").resolve()


def model_cache_path(hub_dir: Path, model_id: str) -> Path:
    return hub_dir / ("models--" + model_id.replace("/", "--"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="互動式解除安裝 transcript-polish。")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--dry-run", action="store_true", help="顯示與詢問，但不實際刪除檔案"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        raise UninstallError(f"找不到 {pyproject}")

    metadata = load_installer_metadata(pyproject)
    command_name = str(metadata.get("command", "transcript-polish"))
    venv_dir = expand_config_path(
        str(metadata.get("venv-dir", "~/.venvs/transcript-polish")),
        "TRANSCRIPT_POLISH_VENV",
    )
    bin_dir = expand_config_path(
        str(metadata.get("bin-dir", "~/bin")), "TRANSCRIPT_POLISH_BIN_DIR"
    )
    known_models = [str(item) for item in metadata.get("known-models", [])]
    wrapper = bin_dir / command_name
    bashrc = Path.home() / ".bashrc"

    print("transcript-polish 互動式解除安裝")
    print("--------------------------------")
    print(f"專案目錄保留：{repo_root}")
    print(f"使用者入口：{wrapper}")
    print(f"專用虛擬環境：{venv_dir}")
    if args.dry_run:
        print("模式：dry-run，不會實際刪除任何內容。")

    wrapper_exists = wrapper.exists() or wrapper.is_symlink()
    wrapper_managed = wrapper_exists and wrapper_is_managed(
        wrapper, command_name, venv_dir
    )
    venv_exists = venv_dir.exists()

    print("\n目前狀態：")
    print(
        f"  - 使用者入口：{'存在（安裝程式管理）' if wrapper_managed else '存在（無法確認來源）' if wrapper_exists else '不存在'}"
    )
    print(f"  - 專用 venv：{'存在' if venv_exists else '不存在'}")
    print("  - repo：不會刪除")
    print("  - Hugging Face 模型快取：預設不刪除")

    if not ask_yes_no("是否進入解除安裝選擇？", default=False):
        print("解除安裝已取消。")
        return 0

    remove_wrapper = False
    if wrapper_exists:
        if wrapper_managed:
            remove_wrapper = ask_yes_no("是否移除使用者入口？", default=True)
        else:
            print(f"警告：{wrapper} 存在，但無法確認由本安裝程式建立。")
            remove_wrapper = ask_yes_no("仍要移除這個檔案嗎？", default=False)

    remove_venv = False
    if venv_exists:
        if not safe_to_remove_venv(venv_dir, repo_root):
            raise UninstallError(f"拒絕刪除不安全的 venv 路徑：{venv_dir}")
        if not (venv_dir / "pyvenv.cfg").exists():
            print(f"警告：{venv_dir} 看起來不像標準 Python venv。")
            confirm = input("若仍要刪除，請輸入 DELETE：").strip()
            remove_venv = confirm == "DELETE"
        else:
            remove_venv = ask_yes_no("是否移除專用虛擬環境？", default=True)

    remove_path = False
    bashrc_text = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""
    if "# transcript-polish user commands" in bashrc_text:
        print(
            "\nPATH 設定可能也供 ~/bin 中其他指令使用，因此預設保留。"
        )
        remove_path = ask_yes_no("是否移除安裝程式加入的 PATH 區塊？", default=False)

    cache_targets: list[Path] = []
    if known_models and ask_yes_no(
        "是否檢查並選擇刪除已知模型的 Hugging Face 快取？", default=False
    ):
        hub_dir = huggingface_hub_dir()
        print(f"模型快取目錄：{hub_dir}")
        print("警告：模型快取可能被其他專案共用，請逐項確認。")
        for model_id in known_models:
            cache_path = model_cache_path(hub_dir, model_id)
            if not cache_path.exists():
                print(f"  - {model_id}：不存在")
                continue
            size = human_size(directory_size(cache_path))
            if ask_yes_no(f"刪除 {model_id} 快取（約 {size}）？", default=False):
                cache_targets.append(cache_path)

    print("\n解除安裝計畫：")
    print(f"  - 使用者入口：{'移除' if remove_wrapper else '保留或不存在'}")
    print(f"  - 專用 venv：{'移除' if remove_venv else '保留或不存在'}")
    print(f"  - PATH 區塊：{'移除' if remove_path else '保留或不存在'}")
    print(f"  - 模型快取：{len(cache_targets)} 個目錄")
    print("  - repo：保留")

    if not any((remove_wrapper, remove_venv, remove_path, cache_targets)):
        print("沒有選擇任何要移除的項目。")
        return 0
    if not ask_yes_no("確認執行以上解除安裝計畫？", default=False):
        print("解除安裝已取消。")
        return 0

    removed: list[str] = []
    if remove_wrapper:
        if not args.dry_run:
            wrapper.unlink(missing_ok=True)
        removed.append(str(wrapper))

    if remove_path:
        if remove_path_block(bashrc, bin_dir, dry_run=args.dry_run):
            removed.append(f"{bashrc} 中的 transcript-polish PATH 區塊")
        else:
            print("注意：找不到可安全移除的完整 PATH 區塊，已保留 .bashrc。")

    for cache_path in cache_targets:
        if not args.dry_run:
            shutil.rmtree(cache_path)
        removed.append(str(cache_path))

    # venv 放在最後刪除，讓前面的檢查與清理可完整執行。
    if remove_venv:
        if not args.dry_run:
            shutil.rmtree(venv_dir)
        removed.append(str(venv_dir))

    print("\n解除安裝完成。" if not args.dry_run else "\ndry-run 完成。")
    if removed:
        print("處理項目：")
        for item in removed:
            print(f"  - {item}")
    print(f"保留 repo：{repo_root}")
    if not cache_targets:
        print(f"模型快取未刪除，可在需要時檢查：{huggingface_hub_dir()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UninstallError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\n解除安裝已取消。", file=sys.stderr)
        else:
            print(f"\n錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)
