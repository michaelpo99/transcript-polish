# SDD/CR-001：media2md consumer contract

狀態：Completed
日期：2026-06-21
適用 repo：transcript-polish

## 1. 背景

`transcript-polish` 是 conservative transcript polishing CLI。它的責任是把 ASR raw transcript 整理成可讀、忠實、保留原語氣與資訊順序的繁體中文 Markdown。

`transcribe-audio` 將新增 `media2md` wrapper，負責把 media 轉成 raw transcript，再呼叫 `transcript-polish` 產生 Markdown。

本 CR 不要求合併 repo，也不要求 `transcript-polish` 依賴 `transcribe-audio`。本 CR 的目標是讓 `transcript-polish` 成為穩定的 pipeline consumer。

## 2. pipeline 目標 layout

`media2md ./meeting` 的預期輸出：

```text
meeting/
├── meeting.mp4
├── transcript/
│   ├── meeting.txt
│   ├── _run-summary.txt
│   └── _environment.txt
└── polished/
    ├── meeting.md
    ├── _run-summary.txt
    └── _environment.txt
```

其中：

- `meeting/transcript/` 是 raw transcript 目錄，由 `transcribe-audio` 產生。
- `meeting/polished/` 是 polished Markdown 目錄，由 `transcript-polish` 產生。

`transcript-polish` 不應假設來源一定來自 `transcribe-audio`；但它應能穩定處理由 `transcribe-audio` 產生的 transcript directory。

## 3. 現況與問題

### 3.1 `--output-dir` 已可支援 pipeline

目前 `transcript-polish` 已支援：

```bash
transcript-polish --dir ./meeting/transcript --output-dir ./meeting/polished
```

因此 `media2md` 可以直接以 absolute path 呼叫，避免相對路徑語意混淆。

### 3.2 預設輸出仍可保留 `formatted/`

`transcript-polish` 獨立使用時，預設輸出到來源目錄下的 `formatted/` 是合理的。

本 CR 不要求改變既有預設，避免破壞舊使用習慣。

pipeline 場景應由 caller 明確指定：

```bash
--output-dir ./meeting/polished
```

### 3.3 control files 排除規則需收斂

`transcribe-audio` 的 transcript 目錄可能包含：

```text
_run-summary.txt
_environment.txt
_failed-files.txt
```

`transcript-polish` 不應把這些控制檔當成逐字稿處理。

目前已排除部分控制檔，但 pipeline contract 應明文化：

```text
所有檔名以 _ 開頭的 .txt / .md 控制檔，預設都不應被 polish。
```

建議修改：

```text
should_skip_input(path, default_output_dir)
```

加入：

```text
if path.name.startswith("_"):
    return True
```

這比只列 `_run-summary.txt`、`_environment.txt` 更穩定。

## 4. 本 repo 需要新增或修改的功能

### 4.1 文件新增 pipeline 用法

README 與 docs/INSTALL.md 應新增一段：

```bash
transcript-polish --dir ./meeting/transcript --output-dir ./meeting/polished
```

並說明這是供 `media2md` 或手動 pipeline 使用。

### 4.2 排除所有 underscore control files

建議將 skip 規則改為：

```text
- 跳過 hidden files。
- 跳過檔名以 `_` 開頭的 .txt / .md。
- 跳過預設輸出目錄 formatted/ 內的檔案。
```

這可避免 `_failed-files.txt`、未來 `_metadata.txt`、`_warnings.md` 被當成逐字稿整理。

### 4.3 保留 `formatted/` 預設，不改成 `polished/`

雖然 pipeline 使用 `polished/`，但不建議改變 standalone 預設值。

原因：

- `formatted/` 是現有行為。
- `polished/` 是 pipeline layout 的約定。
- 由 `media2md` 明確傳 `--output-dir` 更清楚，也更不破壞舊使用者。

### 4.4 可選新增 `--check`

`media2md` 若要在執行前檢查 polish 環境，目前只能依賴：

```bash
transcript-polish --help
```

建議未來新增：

```bash
transcript-polish --check
```

用途：

- 檢查 Python package 可匯入。
- 檢查 transformers / torch / CUDA / quantization 狀態。
- 顯示目前預設 mode、model、quantization。
- 不載入大型模型或不執行實際 polish；若需要深度檢查，可另加 `--check-load-model`。

第一版 `media2md` 可以不依賴此功能；但它是後續提升 UX 的合理方向。

### 4.5 可選新增 pipeline summary metadata

目前 `transcript-polish` 已會產生 `_run-summary.txt` 與 `_environment.txt`。

未來可在 summary 中加入：

```text
input_dir=...
output_dir=...
pipeline_caller=media2md 或空值
```

這不是第一版必要項目，但有助於排查 pipeline 問題。

## 5. 不納入本次 CR 的事項

本 CR 不做：

- 讓 `transcript-polish` 直接呼叫 `transcribe-audio`。
- 合併 repo。
- 建立第三個 orchestration repo。
- 改變 conservative polishing 原則。
- 產生摘要、會議紀錄、決議或待辦。

## 6. 驗收標準

### 6.1 手動 pipeline 可用

給定：

```text
meeting/transcript/meeting.txt
```

執行：

```bash
transcript-polish --dir ./meeting/transcript --output-dir ./meeting/polished
```

應產生：

```text
meeting/polished/meeting.md
```

### 6.2 控制檔不被處理

給定：

```text
meeting/transcript/_run-summary.txt
meeting/transcript/_environment.txt
meeting/transcript/_failed-files.txt
```

執行 polish 後，不應產生：

```text
meeting/polished/_run-summary.md
meeting/polished/_environment.md
meeting/polished/_failed-files.md
```

### 6.3 standalone 行為不破壞

以下既有用法仍可用：

```bash
transcript-polish --dir ./transcript
```

若未指定 `--output-dir`，仍輸出到：

```text
./transcript/formatted/
```

### 6.4 media2md 可呼叫

`media2md` 應能透過：

```bash
transcript-polish --dir <target>/transcript --output-dir <target>/polished
```

把 raw transcript 轉成 polished Markdown。

## 7. 建議實作順序

1. 修改 skip rule，排除所有 `_` 開頭控制檔。
2. 更新 README 與 docs/INSTALL.md，加入 pipeline 用法。
3. 視需要新增 `--check`。
4. 視需要擴充 summary metadata。
5. 與 `transcribe-audio` 的 `media2md` 做一次手動整合測試。
