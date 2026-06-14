#!/usr/bin/env python3
"""Interactive package synchronizer for transcript-polish.

This helper is started by scripts/install.sh with the target virtual
environment's Python interpreter. It reads pyproject.toml, synchronizes core
and optional dependencies, installs the local project, and creates a user-facing
wrapper command.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


class InstallError(RuntimeError):
    pass


def run(
    command: list[str], *, check: bool = True, quiet: bool = False
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(shlex.quote(part) for part in command)
    if not quiet:
        print(f"  $ {printable}", flush=True)
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    )


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


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    if not match:
        raise InstallError(f"無法從 requirement 解析套件名稱：{requirement}")
    return match.group(1)


def installed_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def load_pyproject(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except Exception as exc:
        raise InstallError(f"無法讀取 {path}：{exc}") from exc


def install_requirements(requirements: Iterable[str], label: str) -> None:
    requirement_list = list(requirements)
    if not requirement_list:
        print(f"[略過] {label}：沒有套件。")
        return

    print(f"\n[安裝] {label}")
    for requirement in requirement_list:
        name = requirement_name(requirement)
        version = installed_version(name)
        if version:
            print(f"  - {requirement}（目前 {version}；若已符合條件，pip 不會重裝）")
        else:
            print(f"  - {requirement}（尚未安裝）")

    run([sys.executable, "-m", "pip", "install", *requirement_list])


def uninstall_unselected_packages(
    optional_groups: dict[str, list[str]],
    selected_groups: set[str],
    core_requirements: list[str],
) -> None:
    required_names = {
        normalize_name(requirement_name(requirement)) for requirement in core_requirements
    }
    for group_name in selected_groups:
        required_names.update(
            normalize_name(requirement_name(requirement))
            for requirement in optional_groups[group_name]
        )

    remove_names: list[str] = []
    for group_name, requirements in optional_groups.items():
        if group_name in selected_groups:
            continue
        for requirement in requirements:
            package_name = requirement_name(requirement)
            if normalize_name(package_name) in required_names:
                continue
            if installed_version(package_name) is not None:
                remove_names.append(package_name)

    unique_remove_names = list(dict.fromkeys(remove_names))
    if not unique_remove_names:
        print("\n[同步] 未選取的 optional 套件目前都沒有安裝，不需移除。")
        return

    print("\n[移除] 以下套件屬於未選取的 optional group：")
    for package_name in unique_remove_names:
        print(f"  - {package_name} {installed_version(package_name) or ''}".rstrip())
    run([sys.executable, "-m", "pip", "uninstall", "-y", *unique_remove_names])
    print("  註：只移除 optional group 直接列出的套件；共用或傳遞相依套件可能保留。")


def inspect_torch() -> tuple[str | None, bool, str]:
    version = installed_version("torch")
    if version is None:
        return None, False, ""

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import torch; "
                "ok=bool(torch.cuda.is_available()); "
                "name=torch.cuda.get_device_name(0) if ok else ''; "
                "print(('true' if ok else 'false') + '\\t' + name)"
            ),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if probe.returncode != 0:
        return version, False, ""
    cuda_text, _, gpu_name = probe.stdout.strip().partition("\t")
    return version, cuda_text == "true", gpu_name


def ensure_torch(torch_requirement: str) -> tuple[str | None, bool, str]:
    print("\n[PyTorch] 模型執行引擎")
    print("  PyTorch 未直接列入一般 dependencies，因為 CPU / CUDA 環境可能需要不同版本。")
    version, cuda_available, gpu_name = inspect_torch()
    if version:
        print(f"  已安裝 torch {version}。")
        if cuda_available:
            print(f"  CUDA 可用，GPU：{gpu_name}")
        else:
            print("  注意：目前 torch.cuda.is_available() 為 False。")
        return version, cuda_available, gpu_name

    print("  目前虛擬環境尚未安裝 torch。")
    print(
        "  可由安裝程式執行一般的 `pip install torch`；"
        "若你需要指定特殊 CUDA wheel，請選否後依 PyTorch 官方方式安裝。"
    )
    if ask_yes_no(f"是否現在安裝 {torch_requirement}？", default=True):
        run([sys.executable, "-m", "pip", "install", torch_requirement])
        version, cuda_available, gpu_name = inspect_torch()
        if version:
            print(f"  已安裝 torch {version}。")
        if cuda_available:
            print(f"  CUDA 可用，GPU：{gpu_name}")
        else:
            print("  注意：torch 已安裝，但 CUDA 目前不可用；仍可使用 CPU，速度會較慢。")
        return version, cuda_available, gpu_name

    print("  已略過 torch。CLI 可安裝，但正式模型推論前仍需補裝 PyTorch。")
    return None, False, ""


def choose_optional_groups(
    optional_groups: dict[str, list[str]],
    installer_metadata: dict[str, Any],
    cuda_available: bool,
) -> set[str]:
    if not optional_groups:
        print("\n[Optional] pyproject.toml 沒有 optional dependency group。")
        return set()

    group_metadata = installer_metadata.get("optional-groups", {})
    selected: set[str] = set()
    print("\n[Optional] 請選擇要安裝的額外功能")
    print("  選擇『否』時，若該 group 的直接套件已存在，安裝程式會將它們移除。")

    for group_name, requirements in optional_groups.items():
        metadata_for_group = group_metadata.get(group_name, {})
        description = metadata_for_group.get("description", "未提供說明")
        default = bool(metadata_for_group.get("default", False))
        if group_name == "quantization" and not cuda_available:
            default = False

        print(f"\n  [{group_name}] {description}")
        print("  套件：")
        for requirement in requirements:
            print(f"    - {requirement}")
        if group_name == "quantization" and not cuda_available:
            print("  目前未偵測到可用 CUDA，因此預設選擇否。")

        if ask_yes_no(f"是否安裝 optional group `{group_name}`？", default=default):
            selected.add(group_name)

    return selected


def install_local_project(
    repo_root: Path, project_name: str, project_version: str, command_name: str
) -> None:
    current_version = installed_version(project_name)
    command_path = Path(sys.executable).parent / command_name
    if current_version == project_version and command_path.is_file():
        print(
            f"\n[略過] {project_name} {project_version} 已安裝，"
            "且指令入口存在；版本相同不重新安裝。"
        )
        return

    if current_version:
        print(f"\n[安裝] 專案版本將由 {current_version} 更新為 {project_version}。")
    else:
        print(f"\n[安裝] 安裝 {project_name} {project_version}。")
    run([sys.executable, "-m", "pip", "install", "--no-deps", str(repo_root)])


def shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_wrapper(venv_dir: Path, command_name: str) -> str:
    default_venv = shell_single_quote(str(venv_dir))
    return f"""#!/usr/bin/env bash
set -euo pipefail

DEFAULT_VENV={default_venv}
VENV_DIR="${{TRANSCRIPT_POLISH_VENV:-$DEFAULT_VENV}}"
ENTRY="$VENV_DIR/bin/{command_name}"

if [[ ! -x "$ENTRY" ]]; then
    echo "錯誤：找不到 {command_name} 執行環境：$ENTRY" >&2
    echo "請回到專案目錄重新執行 bash scripts/install.sh。" >&2
    exit 1
fi

exec "$ENTRY" "$@"
"""


def ensure_wrapper(bin_dir: Path, venv_dir: Path, command_name: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = bin_dir / command_name
    expected = build_wrapper(venv_dir, command_name)

    if wrapper_path.exists():
        try:
            current = wrapper_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            current = ""
        if current == expected:
            print(f"\n[略過] 使用者入口已存在且內容相同：{wrapper_path}")
            return wrapper_path
        if not ask_yes_no(f"{wrapper_path} 已存在且內容不同，是否覆蓋？", default=True):
            print("  保留既有入口。")
            return wrapper_path

    wrapper_path.write_text(expected, encoding="utf-8")
    wrapper_path.chmod(0o755)
    print(f"\n[完成] 已建立使用者入口：{wrapper_path}")
    return wrapper_path


def ensure_path(bin_dir: Path) -> None:
    path_entries = [
        Path(entry).expanduser().resolve()
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    ]
    resolved_bin = bin_dir.expanduser().resolve()
    if resolved_bin in path_entries:
        print(f"[PATH] {bin_dir} 已在 PATH 中。")
        return

    print(f"[PATH] {bin_dir} 尚未在目前 PATH 中。")
    bashrc = Path.home() / ".bashrc"
    if not ask_yes_no(f"是否將 {bin_dir} 加入 {bashrc}？", default=True):
        print(f"  請自行加入：export PATH=\"{bin_dir}:$PATH\"")
        return

    if bin_dir == Path.home() / "bin":
        export_line = 'export PATH="$HOME/bin:$PATH"'
    else:
        export_line = f"export PATH={shell_single_quote(str(bin_dir))}:\"$PATH\""

    existing = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""
    if export_line not in existing.splitlines():
        with bashrc.open("a", encoding="utf-8") as stream:
            if existing and not existing.endswith("\n"):
                stream.write("\n")
            stream.write("\n# transcript-polish user commands\n")
            stream.write(export_line + "\n")
        print(f"  已更新 {bashrc}。")
    else:
        print(f"  {bashrc} 已包含相同設定。")
    print(f"  請執行 `source {bashrc}` 或開啟新的 shell。")


def validate_install(command_name: str, selected_groups: set[str]) -> None:
    print("\n[驗證] 檢查安裝結果")
    command_path = Path(sys.executable).parent / command_name
    if not command_path.is_file():
        raise InstallError(f"找不到虛擬環境內的指令入口：{command_path}")
    run([str(command_path), "--help"], quiet=True)
    print(f"  - {command_name} --help：成功")

    version, cuda_available, gpu_name = inspect_torch()
    if version:
        print(f"  - torch {version}：已安裝")
        print(f"  - CUDA：{'可用（' + gpu_name + '）' if cuda_available else '不可用'}")
    else:
        print("  - torch：尚未安裝")

    if "quantization" in selected_groups:
        missing = [
            name
            for name in ("accelerate", "bitsandbytes")
            if installed_version(name) is None
        ]
        if missing:
            raise InstallError(f"量化功能套件缺失：{', '.join(missing)}")
        probe = subprocess.run(
            [sys.executable, "-c", "import accelerate, bitsandbytes"],
            check=False,
            text=True,
            capture_output=True,
        )
        if probe.returncode != 0:
            raise InstallError(
                "量化功能套件已安裝但無法 import：\n" + probe.stdout + probe.stderr
            )
        print("  - 4bit 量化依賴：已安裝且可 import")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise InstallError("pip check 發現相依性問題：\n" + result.stdout + result.stderr)
    print("  - pip check：成功")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="同步 transcript-polish 虛擬環境與使用者指令入口。"
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--venv-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    venv_dir = args.venv_dir.expanduser().resolve()
    pyproject_path = repo_root / "pyproject.toml"
    pyproject = load_pyproject(pyproject_path)

    project = pyproject.get("project", {})
    project_name = str(project.get("name", "")).strip()
    project_version = str(project.get("version", "")).strip()
    core_requirements = list(project.get("dependencies", []))
    optional_groups = {
        str(name): list(requirements)
        for name, requirements in project.get("optional-dependencies", {}).items()
    }
    installer_metadata = (
        pyproject.get("tool", {}).get("transcript-polish", {}).get("installer", {})
    )

    if not project_name or not project_version:
        raise InstallError("pyproject.toml 缺少 project.name 或 project.version。")

    command_name = str(installer_metadata.get("command", project_name))
    bin_dir_value = os.environ.get(
        "TRANSCRIPT_POLISH_BIN_DIR",
        str(installer_metadata.get("bin-dir", "~/bin")),
    )
    bin_dir = Path(bin_dir_value).expanduser().resolve()
    torch_requirement = str(installer_metadata.get("torch-requirement", "torch"))

    print("\n========================================")
    print(f"安裝 {project_name} {project_version}")
    print("========================================")
    print(f"專案目錄：{repo_root}")
    print(f"虛擬環境：{venv_dir}")
    print(f"使用者指令目錄：{bin_dir}")
    print("安裝程式會依 pyproject.toml 同步核心與 optional 套件。")

    _, cuda_available, _ = ensure_torch(torch_requirement)
    install_requirements(core_requirements, "核心 dependencies")
    selected_groups = choose_optional_groups(
        optional_groups, installer_metadata, cuda_available
    )
    uninstall_unselected_packages(
        optional_groups, selected_groups, core_requirements
    )
    for group_name in optional_groups:
        if group_name in selected_groups:
            install_requirements(
                optional_groups[group_name], f"optional group `{group_name}`"
            )

    install_local_project(repo_root, project_name, project_version, command_name)
    ensure_wrapper(bin_dir, venv_dir, command_name)
    ensure_path(bin_dir)
    validate_install(command_name, selected_groups)

    print("\n========================================")
    print("安裝完成")
    print("========================================")
    print(f"直接執行：{command_name} --help")
    current_path_dirs = {
        Path(entry).expanduser().resolve()
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    }
    if bin_dir.resolve() not in current_path_dirs:
        print("若目前 shell 尚未讀取新的 PATH，請開啟新 shell 或 source ~/.bashrc。")
    print("一般使用不需要 source 虛擬環境；只有開發、pip 管理與測試時才需要。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\n安裝已取消。", file=sys.stderr)
        else:
            print(f"\n錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)
