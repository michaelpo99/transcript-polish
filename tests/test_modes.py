from pathlib import Path

import pytest

from transcript_polish import cli
from transcript_polish.entrypoint import resolve_selection
from transcript_polish.user_config import load_user_mode, write_user_mode


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
