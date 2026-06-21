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

## 模型模式

一般使用者不需要記憶 Hugging Face 模型名稱：

| 模式 | 實際模型 | 定位 |
| --- | --- | --- |
| `standard` | `Qwen/Qwen2.5-3B-Instruct`、無量化 | 速度優先、硬體門檻較低 |
| `quality` | `Qwen/Qwen2.5-7B-Instruct`、4-bit | 品質優先，需要 CUDA 與量化套件 |

未指定模式時，使用安裝程式寫入的使用者預設；若沒有設定檔，內建預設是 `standard`。
若設定檔保留 `quality`，但目前環境缺少量化套件或 CUDA，執行時會自動退回 `standard`。

## 快速安裝

進入 repo 後執行：

```bash
bash scripts/install.sh
```

安裝程式會建立專用 venv、讀取 `pyproject.toml` 詢問 optional groups、建立 `~/bin/transcript-polish`，並詢問是否把 Quality 設為此使用者的預設模式。

安裝後不需要手動啟用 venv：

```bash
transcript-polish --help
transcript-polish --dir ./transcript
transcript-polish --check
```

完整說明：[docs/INSTALL.md](docs/INSTALL.md)

## 常用指令

使用預設模式：

```bash
transcript-polish --dir ./transcript
```

明確使用 Standard：

```bash
transcript-polish --mode standard --dir ./transcript
```

明確使用 Quality：

```bash
transcript-polish --mode quality --dir ./transcript
```

一鍵流程或手動 pipeline：

```bash
transcript-polish --dir ./meeting/transcript --output-dir ./meeting/polished
```

其他參數：

```text
transcript-polish --check
transcript-polish --file <path>
transcript-polish --replace-dict <path>
transcript-polish --style-guide <path>
transcript-polish --prompt-config <path>
transcript-polish --force
```

進階使用者仍可直接指定模型：

```bash
transcript-polish --model <hugging-face-model> --quantization <none|4bit>
```

明確指定的 `--model` 或 `--quantization` 會覆蓋 mode 對應值。執行時 `[config]` 會顯示最後實際使用的 mode、model 與 quantization。

## 使用者設定檔

預設模式儲存在：

```text
~/.config/transcript-polish/config.toml
```

例如：

```toml
mode = "quality"
```

優先順序：

1. 明確指定的 `--model` / `--quantization`
2. CLI 的 `--mode`
3. 使用者設定檔的 `mode`
4. 內建 `standard`

## 核心行為

- 掃描指定目錄第一層的 `.txt` / `.md`
- 預設輸出到來源目錄下的 `formatted/`
- 支援外部 replacements、style guide 與 prompt config
- 輸出 `_run-summary.txt` 與 `_environment.txt`
- `--check` 只做環境與設定檢查，不載入大型模型

## 專案結構

```text
transcript-polish/
├── README.md
├── pyproject.toml
├── bin/
├── scripts/
│   ├── install.sh
│   ├── install.py
│   ├── configure_default_mode.py
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
- 整合流程前置 CR：[docs/SDD-CR-001-integrated-pipeline-readiness.md](docs/SDD-CR-001-integrated-pipeline-readiness.md)
- CR 文件命名規則：`docs/SDD-CR-###-<slug>.md`，同一 repo 內依建立順序遞增編號。
- Bug fix 文件命名規則：`docs/SDD-BUGFIX-###-<slug>.md`，同一 repo 內依建立順序遞增編號。
- 本地 LLM 技術背景：[reference/local-llm-inference-stack.md](reference/local-llm-inference-stack.md)
