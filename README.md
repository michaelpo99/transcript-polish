# transcript-polish

`transcript-polish` 使用本地 LLM 將原始逐字稿整理成台灣繁體 Markdown。

## 功能

- 掃描指定目錄第一層的 `.txt` / `.md`
- 預設輸出到目標目錄下的 `formatted/`
- 可指定 Hugging Face 模型名稱
- 預設支援 `Qwen2.5-3B-Instruct`
- 可選 `--quantization 4bit` 搭配 `Qwen2.5-7B-Instruct`
- 會輸出 `_run-summary.txt` 與 `_environment.txt`

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

## 開發用法

repo 內可直接執行：

```bash
./bin/transcript-polish --help
./bin/transcript-polish --dir ./transcript
```

## 正式安裝

建議建立獨立虛擬環境：

```bash
python3 -m venv "$HOME/.venvs/transcript-polish"
source "$HOME/.venvs/transcript-polish/bin/activate"
python -m pip install --upgrade pip setuptools wheel
pip install torch
pip install .
```

若要使用 `--quantization 4bit`：

```bash
pip install '.[quantization]'
```

安裝後即可直接使用：

```bash
transcript-polish --help
transcript-polish --dir ./transcript
```

## 文件

- 安裝方式：`docs/INSTALL.md`
- 規格：`docs/SDD-transcript-polish.md`
