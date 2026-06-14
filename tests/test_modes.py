from pathlib import Path

import pytest

from transcript_polish import cli
from transcript_polish import entrypoint
from transcript_polish.entrypoint import resolve_selection
from transcript_polish.user_config import (
    get_user_config_path,
    load_user_mode,
    write_user_mode,
)


def make_runtime_info() -> cli.RuntimeInfo:
    return cli.RuntimeInfo(
        python_version="3.12.0",
        torch_version="2.0.0",
        transformers_version="4.57.0",
        accelerate_version="1.14.0",
        bitsandbytes_version="0.49.0",
        cuda_available=True,
        cuda_runtime="12.8",
        gpu_name="Test GPU",
        gpu_vram_mb="10240",
        import_error="",
    )


def make_runtime_info_without_quality() -> cli.RuntimeInfo:
    return cli.RuntimeInfo(
        python_version="3.12.0",
        torch_version="2.0.0",
        transformers_version="4.57.0",
        accelerate_version="",
        bitsandbytes_version="",
        cuda_available=False,
        cuda_runtime="",
        gpu_name="",
        gpu_vram_mb="",
        import_error="",
    )


def test_builtin_default_is_standard(tmp_path: Path):
    selection = resolve_selection(
        [],
        cli_mode=None,
        parsed_model=None,
        parsed_quantization=None,
        config_path=tmp_path / "missing.toml",
    )

    assert selection.mode == "standard"
    assert selection.mode_source == "builtin"
    assert selection.model == "Qwen/Qwen2.5-3B-Instruct"
    assert selection.quantization == "none"


def test_cli_quality_mode_selects_7b_4bit(tmp_path: Path):
    selection = resolve_selection(
        ["--mode", "quality"],
        cli_mode="quality",
        parsed_model=None,
        parsed_quantization=None,
        config_path=tmp_path / "missing.toml",
    )

    assert selection.mode == "quality"
    assert selection.mode_source == "cli"
    assert selection.model == "Qwen/Qwen2.5-7B-Instruct"
    assert selection.quantization == "4bit"


def test_user_config_quality_is_used(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('mode = "quality"\n', encoding="utf-8")

    selection = resolve_selection(
        [],
        cli_mode=None,
        parsed_model=None,
        parsed_quantization=None,
        config_path=config_path,
    )

    assert selection.mode == "quality"
    assert selection.mode_source == "user_config"
    assert selection.model == "Qwen/Qwen2.5-7B-Instruct"
    assert selection.quantization == "4bit"


def test_cli_mode_overrides_user_config(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('mode = "quality"\n', encoding="utf-8")

    selection = resolve_selection(
        ["--mode=standard"],
        cli_mode="standard",
        parsed_model=None,
        parsed_quantization=None,
        config_path=config_path,
    )

    assert selection.mode == "standard"
    assert selection.mode_source == "cli"
    assert selection.model == "Qwen/Qwen2.5-3B-Instruct"
    assert selection.quantization == "none"


def test_explicit_model_and_quantization_override_mode(tmp_path: Path):
    selection = resolve_selection(
        ["--mode", "quality", "--model", "example/model", "--quantization=none"],
        cli_mode="quality",
        parsed_model="example/model",
        parsed_quantization="none",
        config_path=tmp_path / "missing.toml",
    )

    assert selection.mode == "quality"
    assert selection.model == "example/model"
    assert selection.quantization == "none"


def test_single_advanced_option_only_overrides_that_value(tmp_path: Path):
    selection = resolve_selection(
        ["--mode", "quality", "--model=example/model"],
        cli_mode="quality",
        parsed_model="example/model",
        parsed_quantization=None,
        config_path=tmp_path / "missing.toml",
    )

    assert selection.model == "example/model"
    assert selection.quantization == "4bit"


def test_invalid_user_mode_fails_clearly(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('mode = "turbo"\n', encoding="utf-8")

    with pytest.raises(cli.UserFacingError, match="standard 或 quality"):
        resolve_selection(
            [],
            cli_mode=None,
            parsed_model=None,
            parsed_quantization=None,
            config_path=config_path,
        )


def test_broken_toml_fails_clearly(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('mode = "quality"\n[broken\n', encoding="utf-8")

    with pytest.raises(cli.UserFacingError, match="設定檔格式錯誤"):
        resolve_selection(
            [],
            cli_mode=None,
            parsed_model=None,
            parsed_quantization=None,
            config_path=config_path,
        )


def test_write_user_mode_preserves_other_fields(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'mode = "standard"\ncustom_value = "keep"\n\n[future]\nenabled = true\n',
        encoding="utf-8",
    )

    write_user_mode("quality", config_path)
    text = config_path.read_text(encoding="utf-8")

    assert load_user_mode(config_path) == "quality"
    assert 'custom_value = "keep"' in text
    assert "[future]" in text
    assert "enabled = true" in text


def test_mode_aware_entrypoint_reports_and_records_quality(
    tmp_path: Path, monkeypatch, capsys
):
    input_path = tmp_path / "sample.txt"
    input_path.write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "formatted"
    output_dir.mkdir()
    (output_dir / "sample.md").write_text("done\n", encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(
        cli,
        "load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    exit_code = entrypoint.main(["--mode", "quality", "--dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[config] mode=quality" in captured.out
    assert "[config] mode_source=cli" in captured.out
    assert "[config] model=Qwen/Qwen2.5-7B-Instruct" in captured.out
    assert "[config] quantization=4bit" in captured.out
    assert "mode=quality" in (output_dir / "_run-summary.txt").read_text(encoding="utf-8")
    assert "mode_source=cli" in (output_dir / "_environment.txt").read_text(
        encoding="utf-8"
    )


def test_user_config_quality_falls_back_when_runtime_lacks_quality(
    tmp_path: Path, monkeypatch, capsys
):
    input_path = tmp_path / "sample.txt"
    input_path.write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "formatted"
    output_dir.mkdir()
    (output_dir / "sample.md").write_text("done\n", encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    config_path = get_user_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('mode = "quality"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info_without_quality)
    monkeypatch.setattr(
        cli,
        "load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    exit_code = entrypoint.main(["--dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[config] mode=standard" in captured.out
    assert "[config] mode_source=user_config_fallback" in captured.out
    assert "[config] model=Qwen/Qwen2.5-3B-Instruct" in captured.out
    assert "[config] quantization=none" in captured.out
