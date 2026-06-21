import pytest

from transcript_polish import cli


def test_resolve_output_dir_relative_to_base_dir():
    base_dir = cli.Path("/tmp/transcript-input")
    args = cli.argparse.Namespace(output_dir="results/final")

    output_dir = cli.resolve_output_dir(args, base_dir, layout="legacy")

    assert output_dir == base_dir / "results" / "final"


def test_auto_layout_uses_sidecar_paths_for_transcript_input():
    base_dir = cli.Path("/tmp/Meeting.transcript")
    args = cli.argparse.Namespace(
        output_dir=None,
        meta_output=None,
        no_meta=False,
        layout="auto",
    )

    output_dir = cli.resolve_output_dir(args, base_dir, layout="sidecar")
    meta_dir = cli.resolve_meta_dir(args, base_dir, layout="sidecar", output_dir=output_dir)

    assert output_dir == cli.Path("/tmp/Meeting.polished")
    assert meta_dir == cli.Path("/tmp/Meeting.meta")


def test_legacy_layout_keeps_meta_in_output_dir():
    base_dir = cli.Path("/tmp/transcript-input")
    args = cli.argparse.Namespace(
        output_dir=None,
        meta_output=None,
        no_meta=False,
        layout="legacy",
    )

    output_dir = cli.resolve_output_dir(args, base_dir, layout="legacy")
    meta_dir = cli.resolve_meta_dir(args, base_dir, layout="legacy", output_dir=output_dir)

    assert output_dir == base_dir / "formatted"
    assert meta_dir == output_dir


def test_processing_context_skips_control_files_by_default(tmp_path):
    regular = tmp_path / "meeting.txt"
    summary = tmp_path / "_run-summary.txt"
    env = tmp_path / "_environment.txt"
    failed = tmp_path / "_failed-files.txt"
    transcribe_summary = tmp_path / "transcribe-run-summary.txt"
    regular.write_text("hello", encoding="utf-8")
    summary.write_text("sum", encoding="utf-8")
    env.write_text("env", encoding="utf-8")
    failed.write_text("failed", encoding="utf-8")
    transcribe_summary.write_text("transcribe", encoding="utf-8")

    args = cli.argparse.Namespace(
        file=None,
        dir=str(tmp_path),
        layout="legacy",
        output_dir=None,
        meta_output=None,
        no_meta=False,
        include_control_files=False,
    )
    ctx = cli.resolve_processing_context(args)

    assert ctx.files == [regular.resolve()]


def test_processing_context_can_include_control_files(tmp_path):
    regular = tmp_path / "meeting.txt"
    summary = tmp_path / "_run-summary.txt"
    regular.write_text("hello", encoding="utf-8")
    summary.write_text("sum", encoding="utf-8")

    args = cli.argparse.Namespace(
        file=None,
        dir=str(tmp_path),
        layout="legacy",
        output_dir=None,
        meta_output=None,
        no_meta=False,
        include_control_files=True,
    )
    ctx = cli.resolve_processing_context(args)

    assert ctx.files == [summary.resolve(), regular.resolve()]


def test_same_stem_txt_and_md_conflict(tmp_path):
    first = tmp_path / "lesson01.txt"
    second = tmp_path / "lesson01.md"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    output_dir = tmp_path / "formatted"

    with pytest.raises(cli.UserFacingError) as exc_info:
        cli.build_file_jobs([first, second], output_dir, force=False)

    assert "輸出檔名衝突" in str(exc_info.value)
