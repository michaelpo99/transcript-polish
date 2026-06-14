from transcript_polish import cli


def make_loaded_model() -> cli.LoadedModel:
    return cli.LoadedModel(
        tokenizer=None,
        model=None,
        device="cpu",
        dtype_name="float32",
        quantization="none",
        input_device="cpu",
        model_memory_bytes="1",
    )


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


def test_apply_replacements_is_non_chained():
    result = cli.apply_replacements("POA", {"POA": "PUA", "PUA": "X"})
    assert result == "PUA"


def test_main_does_not_apply_removed_builtin_replacements(tmp_path, monkeypatch):
    input_path = tmp_path / "sample.txt"
    input_path.write_text("POA AIP 物理資料\n", encoding="utf-8")

    monkeypatch.setattr(cli, "load_model", lambda *_args, **_kwargs: make_loaded_model())
    monkeypatch.setattr(cli, "detect_runtime_info", make_runtime_info)
    monkeypatch.setattr(cli, "load_opencc_converter", lambda: None)
    monkeypatch.setattr(
        cli,
        "process_text",
        lambda content, *_args, **_kwargs: content,
    )

    exit_code = cli.main(["--dir", str(tmp_path)])

    assert exit_code == 0
    output_path = tmp_path / "formatted" / "sample.md"
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8").strip() == "POA AIP 物理資料"
