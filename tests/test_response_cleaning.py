from transcript_polish import cli


def test_clean_response_removes_code_fence_and_wrapper():
    raw = """```markdown
以下是整理後的逐字稿：

第一段。
```
"""

    assert cli.clean_response(raw) == "第一段。"


def test_clean_response_keeps_legitimate_trailing_sentence():
    raw = "這一段談的是修正完成率，不是結尾包裝文字。"

    assert cli.clean_response(raw) == raw
