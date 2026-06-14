# transcript-polish

`transcript-polish` 是一個 **conservative transcript polishing** CLI。

它的目標不是把逐字稿改寫成文章，也不是產生會議紀錄，而是：

> 將 ASR 原始逐字稿整理成可讀、忠實、保留講者原本語氣與詞彙選擇的繁體中文 Markdown。

## 產品定位

`transcript-polish` 可以做：

- 簡體轉繁體
- 補標點、斷句與分段
- 修正高度確定的 ASR 錯字
- 適度加入方便閱讀的標題
- 保留口語、中英夾雜、講者標記、數字與原始資訊順序

`transcript-polish` 不應做：

- 摘要或濃縮
- 改寫成正式文章
- 為了通順而翻譯原本正確的英文口語
- 為了好讀而新增原文沒有的資訊
- 產生會議紀錄、決議或待辦事項

建議的處理管線是：

```text
WhisperX
-> 原始逐字稿
-> transcript-polish
-> 忠實且可讀的逐字稿
-> meeting-minutes / summarizer
```

## 目前模型策略

| 模式 | 模型 | 定位 |
| --- | --- | --- |
| Standard / Fast | `Qwen/Qwen2.5-3B-Instruct` | 低門檻、速度優先 |
| Quality | `Qwen/Qwen2.5-7B-Instruct` + `--quantization 4bit` | 正式輸出、較佳語意與分段 |

## CLI 概覽

```bash
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

目前核心行為：

- 掃描指定目錄第一層的 `.txt` / `.md`
- 預設輸出到來源目錄下的 `formatted/`
- 支援外部 `--replace-dict`
- 支援外部 `--style-guide`
- 支援外部 `--prompt-config`（JSON）
- 輸出 `_run-summary.txt` 與 `_environment.txt`

## 專案結構

```text
transcript-polish/
├── .gitignore
├── README.md
├── pyproject.toml
├── bin/
│   └── transcript-polish
├── docs/
│   ├── INSTALL.md
│   └── SDD-transcript-polish.md
└── src/
    └── transcript_polish/
        ├── __init__.py
        └── cli.py
```

## 開發與安裝

repo 內開發入口：

```bash
./bin/transcript-polish --help
./bin/transcript-polish --dir ./transcript
```

正式安裝與部署方式請看：

- [docs/INSTALL.md](docs/INSTALL.md)

規格與下一版方向請看：

- [docs/SDD-transcript-polish.md](docs/SDD-transcript-polish.md)
