# transcript-polish

`transcript-polish` 是一個 **conservative transcript polishing** CLI。

它的目標不是把逐字稿改寫成文章，也不是產生會議紀錄，而是：

> 將 ASR 原始逐字稿整理成可讀、忠實、保留講者原本語氣與詞彙選擇的繁體中文 Markdown。

## 產品定位

可以做：

- 簡體轉繁體
- 補標點、斷句與分段
- 修正高度確定的 ASR 錯字
- 適度加入方便閱讀的標題
- 保留口語、中英夾雜、講者標記、數字與資訊順序

不應做：

- 摘要或濃縮
- 改寫成正式文章
- 翻譯原本正確的英文口語
- 新增原文沒有的資訊
- 產生會議紀錄、決議或待辦事項

## 模型策略

| 模式 | 模型 | 定位 |
| --- | --- | --- |
| Standard / Fast | `Qwen/Qwen2.5-3B-Instruct` | 低門檻、速度優先 |
| Quality | `Qwen/Qwen2.5-7B-Instruct` + `--quantization 4bit` | 正式輸出、較佳語意與分段 |

## 快速安裝

進入 repo 後執行：

```bash
bash scripts/install.sh
```

安裝程式會建立專用 venv、讀取 `pyproject.toml` 詢問 optional groups，並建立 `~/bin/transcript-polish`。

安裝後一般使用者不需要手動啟用 venv：

```bash
transcript-polish --help
transcript-polish --dir ./transcript
```

完整說明：[docs/INSTALL.md](docs/INSTALL.md)

## CLI 概覽

```text
transcript-polish
transcript-polish --file <path>
transcript-polish --dir <path>
transcript-polish --model <name>
transcript-polish --quantization <mode>
transcript-polish --replace-dict <path>
transcript-polish --style-guide <path>
transcript-polish --prompt-config <path>
transcript-polish --force
```

核心行為：

- 掃描指定目錄第一層的 `.txt` / `.md`
- 預設輸出到來源目錄下的 `formatted/`
- 支援外部 replacements、style guide 與 prompt config
- 輸出 `_run-summary.txt` 與 `_environment.txt`

## Quality 模式

安裝時選擇 `quantization` 後：

```bash
transcript-polish --dir ./transcript \
  --model Qwen/Qwen2.5-7B-Instruct \
  --quantization 4bit
```

## 專案結構

```text
transcript-polish/
├── README.md
├── pyproject.toml
├── bin/
├── scripts/
│   ├── install.sh
│   ├── install.py
│   └── uninstall.sh
├── docs/
├── reference/
└── src/transcript_polish/
```

## 開發

```bash
source "$HOME/.venvs/transcript-polish/bin/activate"
python -m pip install -e '.[dev,quantization]'
pytest
```

## 文件

- 安裝與部署：[docs/INSTALL.md](docs/INSTALL.md)
- 系統設計：[docs/SDD-transcript-polish.md](docs/SDD-transcript-polish.md)
- 本地 LLM 技術背景：[reference/local-llm-inference-stack.md](reference/local-llm-inference-stack.md)
