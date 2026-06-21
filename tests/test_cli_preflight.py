from transcript_polish import cli


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


def test_all_skipped_does_not_load_model_and_reports_zero_queued(
    tmp_path, monkeypatch, capsys
):
    input_path = tmp_path / "sample.txt"
    input_path.write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "formatted"
    output_dir.mkdir()
    (output_dir / "sample.md").write_text("done\n", encoding="utf-8")

    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(
        cli,
        "load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    exit_code = cli.main(["--dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[run] queued=0" in captured.out


def test_prompt_config_is_validated_before_all_skipped(tmp_path, capsys):
    input_path = tmp_path / "sample.txt"
    input_path.write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "formatted"
    output_dir.mkdir()
    (output_dir / "sample.md").write_text("done\n", encoding="utf-8")

    exit_code = cli.main(
        [
            "--dir",
            str(tmp_path),
            "--prompt-config",
            str(tmp_path / "missing.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "prompt config 不存在" in captured.err


def test_check_does_not_load_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    exit_code = cli.main(["--check"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[check] transcript-polish 環境檢查" in captured.out
    assert "[check] 不會載入大型模型" in captured.out


def test_directory_scan_skips_underscore_control_files(tmp_path):
    regular = tmp_path / "meeting.txt"
    run_summary = tmp_path / "_run-summary.txt"
    environment = tmp_path / "_environment.txt"
    failed = tmp_path / "_failed-files.txt"
    hidden = tmp_path / ".hidden.txt"
    regular.write_text("hello", encoding="utf-8")
    run_summary.write_text("summary", encoding="utf-8")
    environment.write_text("env", encoding="utf-8")
    failed.write_text("failed", encoding="utf-8")
    hidden.write_text("hidden", encoding="utf-8")

    files, base_dir, _source_label = cli.resolve_input_files(
        cli.argparse.Namespace(file=None, dir=str(tmp_path))
    )

    assert base_dir == tmp_path.resolve()
    assert files == [regular.resolve()]
