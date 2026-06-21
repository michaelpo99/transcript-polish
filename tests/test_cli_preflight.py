from transcript_polish import cli, entrypoint


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
    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(cli, "load_opencc_converter", lambda: object())
    monkeypatch.setattr(
        cli,
        "load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    exit_code = cli.main(["--check"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[check] transcript-polish 環境檢查" in captured.out
    assert "[check] opencc=available" in captured.out
    assert "[check] 不會載入大型模型" in captured.out


def test_check_fails_when_opencc_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(cli, "load_opencc_converter", lambda: None)

    exit_code = cli.main(["--check"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "opencc" in captured.err


def test_quality_check_requires_optional_packages(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "detect_runtime_info",
        lambda: cli.RuntimeInfo(
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
        ),
    )
    monkeypatch.setattr(cli, "load_opencc_converter", lambda: object())

    exit_code = entrypoint.main(["--mode", "quality", "--check"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "accelerate" in captured.err
    assert "bitsandbytes" in captured.err


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

    ctx = cli.resolve_processing_context(
        cli.argparse.Namespace(
            file=None,
            dir=str(tmp_path),
            layout="legacy",
            output_dir=None,
            meta_output=None,
            no_meta=False,
            include_control_files=False,
        )
    )

    assert ctx.base_dir == tmp_path.resolve()
    assert ctx.files == [regular.resolve()]


def test_sidecar_layout_writes_polish_meta_files_without_loading_model(
    tmp_path, monkeypatch, capsys
):
    input_dir = tmp_path / "Meeting.transcript"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "Meeting.polished"
    output_dir.mkdir()
    (output_dir / "a.md").write_text("done\n", encoding="utf-8")

    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(
        cli,
        "load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    exit_code = cli.main(["--dir", str(input_dir), "--layout", "auto"])
    captured = capsys.readouterr()

    assert exit_code == 0
    meta_dir = tmp_path / "Meeting.meta"
    assert (meta_dir / "polish-run-summary.txt").is_file()
    assert (meta_dir / "polish-environment.txt").is_file()
    assert (meta_dir / "polish-failed-files.txt").is_file()
    assert "[result] output_dir=" in captured.out
    assert "[result] meta_dir=" in captured.out


def test_no_meta_suppresses_metadata_files(tmp_path, monkeypatch):
    input_dir = tmp_path / "Meeting.transcript"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "Meeting.polished"
    output_dir.mkdir()
    (output_dir / "a.md").write_text("done\n", encoding="utf-8")

    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(
        cli,
        "load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    exit_code = cli.main(["--dir", str(input_dir), "--layout", "auto", "--no-meta"])

    assert exit_code == 0
    assert not (tmp_path / "Meeting.meta").exists()
