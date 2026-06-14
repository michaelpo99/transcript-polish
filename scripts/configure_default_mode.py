#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata as metadata
import sys

from transcript_polish.user_config import (
    UserConfigError,
    get_user_config_path,
    load_user_mode,
    write_user_mode,
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


def package_installed(name: str) -> bool:
    try:
        metadata.version(name)
        return True
    except metadata.PackageNotFoundError:
        return False


def cuda_available() -> bool:
    try:
        import torch  # type: ignore
    except Exception:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def main() -> int:
    config_path = get_user_config_path()
    try:
        current_mode = load_user_mode(config_path)
    except UserConfigError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    effective_current_mode = current_mode or "standard"

    quantization_available = package_installed("accelerate") and package_installed(
        "bitsandbytes"
    )
    quality_available = quantization_available and cuda_available()

    print("\n[預設模式] 設定一般執行時使用的模型模式")
    print(f"  設定檔：{config_path}")
    print(f"  目前模式：{current_mode or 'standard（內建預設）'}")

    if quality_available:
        use_quality = ask_yes_no(
            "是否將 Quality 模式（7B、4-bit）設為此使用者的預設模式？",
            default=current_mode == "quality",
        )
        desired_mode = "quality" if use_quality else "standard"
    else:
        desired_mode = "standard"
        if not quantization_available:
            reason = "未安裝完整 quantization 套件"
        else:
            reason = "目前 CUDA 不可用"
        if current_mode == "quality":
            print(f"  {reason}，為避免預設模式無法執行，將改回 standard。")
        else:
            print(f"  {reason}，維持 standard。")

    try:
        written_path = write_user_mode(desired_mode, config_path)
    except UserConfigError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    if effective_current_mode == desired_mode:
        print(f"  mode 維持為 \"{desired_mode}\"。")
    else:
        print(f"  已設定 mode = \"{desired_mode}\"：{written_path}")
    print(f"  目前預設 mode：{desired_mode}")
    print(f"  如需修改，請編輯 {written_path} 的 `mode = \"standard\"` 或 `mode = \"quality\"`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
