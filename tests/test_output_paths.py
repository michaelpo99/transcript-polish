import pytest

from transcript_polish import cli


def test_resolve_output_dir_relative_to_base_dir():
    base_dir = cli.Path("/tmp/transcript-input")
    args = cli.argparse.Namespace(output_dir="results/final")

    output_dir = cli.resolve_output_dir(args, base_dir)

    assert output_dir == base_dir / "results" / "final"


def test_same_stem_txt_and_md_conflict(tmp_path):
    first = tmp_path / "lesson01.txt"
    second = tmp_path / "lesson01.md"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    output_dir = tmp_path / "formatted"

    with pytest.raises(cli.UserFacingError) as exc_info:
        cli.build_file_jobs([first, second], output_dir, force=False)

    assert "輸出檔名衝突" in str(exc_info.value)
