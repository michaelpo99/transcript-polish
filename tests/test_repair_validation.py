from transcript_polish import cli


def test_validate_repair_output_rejects_missing_numbers_and_terms():
    draft = "WhisperX 版本 2.1 在 CUDA 12.1 上可用。"
    repaired = "這個版本可用。"
    original = draft

    assert cli.validate_repair_output(repaired, draft, original) is False


def test_validate_repair_output_uses_original_when_draft_is_empty():
    original = "我覺得這個很 low，feedback 也很多，版本是 2.1。"
    repaired = "我覺得這個很 low，feedback 也很多，版本是 2.1。"

    assert cli.validate_repair_output(repaired, "", original) is True


def test_validate_repair_output_rejects_packaging_text():
    original = "原始內容。"
    repaired = "以下是整理後的內容：\n\n原始內容。"

    assert cli.validate_repair_output(repaired, "原始內容。", original) is False
