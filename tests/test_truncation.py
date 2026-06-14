from pathlib import Path

from transcript_polish import cli, entrypoint
from transcript_polish.generation import output_is_truncated


def make_runtime_info() -> cli.RuntimeInfo:
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


def make_loaded_model() -> cli.LoadedModel:
    return cli.LoadedModel(
        tokenizer=object(),
        model=object(),
        device="cpu",
        dtype_name="float32",
        quantization="none",
        input_device="cpu",
        model_memory_bytes="0",
    )


def test_output_at_limit_without_eos_is_truncated():
    assert output_is_truncated(
        [10, 11, 12, 13],
        max_new_tokens=4,
        eos_token_ids={2},
    )


def test_output_at_limit_with_eos_is_complete():
    assert not output_is_truncated(
        [10, 11, 12, 2],
        max_new_tokens=4,
        eos_token_ids={2},
    )


def test_output_below_limit_is_complete():
    assert not output_is_truncated(
        [10, 11, 12],
        max_new_tokens=4,
        eos_token_ids={2},
    )


def test_failed_file_does_not_stop_later_files(tmp_path: Path, monkeypatch, capsys):
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(cli, "load_model", lambda *_args: make_loaded_model())
    monkeypatch.setattr(cli, "load_opencc_converter", lambda: None)

    def fake_process_text(content, *_args, **_kwargs):
        if content == "first":
            raise cli.UserFacingError(
                "錯誤：模型輸出達到上限 4096 tokens，內容未完整輸出。"
            )
        return "second completed"

    monkeypatch.setattr(cli, "process_text", fake_process_text)

    exit_code = entrypoint.main(["--dir", str(tmp_path)])
    captured = capsys.readouterr()
    output_dir = tmp_path / "formatted"

    assert exit_code == 1
    assert not (output_dir / "a.md").exists()
    assert (output_dir / "b.md").read_text(encoding="utf-8") == "second completed\n"
    assert "[1/2] failed -> a.txt" in captured.out
    assert "[2/2] processing b.txt" in captured.out
    assert "[2/2] done" in captured.out
    assert "success=1" in captured.out
    assert "failed=1" in captured.out
