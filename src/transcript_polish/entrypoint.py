from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from . import cli
from .user_config import UserConfigError, get_user_config_path, load_user_mode


@dataclass(frozen=True)
class ModePreset:
    model: str
    quantization: str


@dataclass(frozen=True)
class ModeSelection:
    mode: str
    mode_source: str
    model: str
    quantization: str


MODE_PRESETS = {
    "standard": ModePreset(
        model="Qwen/Qwen2.5-3B-Instruct",
        quantization="none",
    ),
    "quality": ModePreset(
        model="Qwen/Qwen2.5-7B-Instruct",
        quantization="4bit",
    ),
}
DEFAULT_MODE = "standard"


def option_is_explicit(argv: Sequence[str], option: str) -> bool:
    return any(argument == option or argument.startswith(option + "=") for argument in argv)


def resolve_selection(
    argv: Sequence[str],
    *,
    cli_mode: str | None,
    parsed_model: str | None,
    parsed_quantization: str | None,
    config_path: Path | None = None,
) -> ModeSelection:
    try:
        user_mode = load_user_mode(config_path)
    except UserConfigError as exc:
        raise cli.UserFacingError(f"錯誤：{exc}") from exc

    if cli_mode:
        mode = cli_mode
        mode_source = "cli"
    elif user_mode:
        mode = user_mode
        mode_source = "user_config"
    else:
        mode = DEFAULT_MODE
        mode_source = "builtin"

    preset = MODE_PRESETS[mode]
    model = parsed_model if option_is_explicit(argv, "--model") else preset.model
    quantization = (
        parsed_quantization
        if option_is_explicit(argv, "--quantization")
        else preset.quantization
    )
    return ModeSelection(
        mode=mode,
        mode_source=mode_source,
        model=model or preset.model,
        quantization=quantization or preset.quantization,
    )


def append_mode_metadata(output_dir: Path, selection: ModeSelection) -> None:
    additions = f"mode={selection.mode}\nmode_source={selection.mode_source}\n"
    for filename in ("_run-summary.txt", "_environment.txt"):
        path = output_dir / filename
        if path.is_file():
            with path.open("a", encoding="utf-8") as stream:
                stream.write(additions)


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    state: dict[str, ModeSelection] = {}

    original_build_parser = cli.build_parser
    original_print_run_config = cli.print_run_config
    original_write_summary_files = cli.write_summary_files

    def build_parser_with_mode():
        parser = original_build_parser()
        parser.add_argument(
            "--mode",
            choices=tuple(MODE_PRESETS),
            default=None,
            help=(
                "選擇模型模式：standard 使用 3B、無量化、速度優先；"
                "quality 使用 7B、4-bit、品質優先，需要 CUDA 與 quantization 套件"
            ),
        )
        # 原 CLI 的 model / quantization 有內建預設；在這一層改為 None，
        # 才能辨識使用者是否真的明確指定並套用 mode 優先權。
        parser.set_defaults(model=None, quantization=None)
        original_parse_args = parser.parse_args

        def parse_args_with_mode(args=None, namespace=None):
            actual_argv = list(raw_argv if args is None else args)
            parsed = original_parse_args(args, namespace)
            selection = resolve_selection(
                actual_argv,
                cli_mode=parsed.mode,
                parsed_model=parsed.model,
                parsed_quantization=parsed.quantization,
                config_path=get_user_config_path(),
            )
            parsed.mode = selection.mode
            parsed.mode_source = selection.mode_source
            parsed.model = selection.model
            parsed.quantization = selection.quantization
            state["selection"] = selection
            return parsed

        parser.parse_args = parse_args_with_mode  # type: ignore[method-assign]
        return parser

    def print_run_config_with_mode(*args, **kwargs):
        selection = state["selection"]
        print(f"[config] mode={selection.mode}")
        print(f"[config] mode_source={selection.mode_source}")
        return original_print_run_config(*args, **kwargs)

    def write_summary_files_with_mode(*args, **kwargs):
        result = original_write_summary_files(*args, **kwargs)
        output_dir = kwargs.get("output_dir")
        if output_dir is None and args:
            output_dir = args[0]
        append_mode_metadata(Path(output_dir), state["selection"])
        return result

    cli.build_parser = build_parser_with_mode
    cli.print_run_config = print_run_config_with_mode
    cli.write_summary_files = write_summary_files_with_mode
    try:
        return cli.main(raw_argv)
    except cli.UserFacingError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        cli.build_parser = original_build_parser
        cli.print_run_config = original_print_run_config
        cli.write_summary_files = original_write_summary_files


if __name__ == "__main__":
    raise SystemExit(main())
