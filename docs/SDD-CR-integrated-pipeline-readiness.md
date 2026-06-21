# SDD/CR：整合流程前置修正規格

狀態：Proposed
日期：2026-06-21
適用 repo：transcript-polish

## 1. 背景與目的

`transcript-polish` 目前定位為 conservative transcript polishing CLI，負責將 ASR 原始逐字稿整理成忠實、可讀、保留原語氣與詞彙選擇的繁體中文 Markdown。

未來若要把 `extract-audio`、`transcribe-audio`、`transcript-polish` 合併成同一工具集，合併前必須先讓本 repo 成為穩定的 transcript consumer 與 polished markdown producer。此 CR 不改變模型策略，也不要求立即合併 repo；目標是先修正輸入掃描、輸出路徑與 metadata 邊界，使它能無痛接在 `transcribe-audio` 的 sidecar 輸出後面。

核心原則：

- 只處理正文逐字稿，不處理 summary、environment、failed list 等控制檔。
- 對於 `Meeting.transcript/` 這類整合流程輸入，預設輸出應是 sibling `Meeting.polished/`。
- metadata 應能輸出到獨立 `Meeting.meta/`，避免混入 polished markdown 目錄。
- 保留既有單獨使用情境，讓一般 `transcript-polish --dir ./some-dir` 不被過度假設為整合 pipeline。

## 2. 現況問題

### 2.1 控制檔排除規則不足

目前目錄模式掃描指定目錄第一層 `.txt` 與 `.md`。程式已排除 `_run-summary.txt` 與 `_environment.txt`，但這是列舉式保護，無法涵蓋 `_failed-files.txt` 或未來新增的 control files。

整合流程中，上游可能產生：

```text
_run-summary.txt
_environment.txt
_failed-files.txt
transcribe-run-summary.txt
transcribe-environment.txt
transcribe-failed-files.txt
```

這些都不是逐字稿正文，不應被送進模型。

### 2.2 預設輸出 `formatted/` 會造成階層過深

若上游輸出為：

```text
Meeting.transcript/
  a.txt
  b.txt
```

目前執行：

```bash
transcript-polish --dir ./Meeting.transcript
```

預設會產生：

```text
Meeting.transcript/
  formatted/
    a.md
    b.md
```

整合流程較理想的結構是：

```text
Meeting.transcript/
Meeting.polished/
Meeting.meta/
```

### 2.3 summary/environment 不應混入 polished output

目前 summary 與 environment 會寫在輸出目錄。若未來還有第三階段，這些檔案仍可能被誤掃描。即使目前沒有第三階段，也應把正文輸出與 metadata 輸出分離。

## 3. 目標行為

### 3.1 整合流程預設 layout

當輸入目錄名稱符合 `*.transcript` 時：

```bash
transcript-polish --dir ./Meeting.transcript
```

預設推導：

```text
input_dir=./Meeting.transcript
output_dir=./Meeting.polished
meta_dir=./Meeting.meta
```

目標結構：

```text
Meeting.transcript/
  a.txt
  b.txt

Meeting.polished/
  a.md
  b.md

Meeting.meta/
  polish-run-summary.txt
  polish-environment.txt
  polish-failed-files.txt
```

此規則讓整合流程可以直接串接：

```bash
transcribe-audio ./Meeting
transcript-polish --dir ./Meeting.transcript
```

### 3.2 一般使用情境保留

若輸入目錄名稱不是 `*.transcript`，為避免破壞既有習慣，預設仍可維持：

```bash
transcript-polish --dir ./transcript
```

輸出：

```text
transcript/formatted/
```

因此建議新增：

```text
--layout auto|legacy|sidecar
```

語意：

- `auto`：預設。若輸入目錄 basename 以 `.transcript` 結尾，採 sidecar；否則採 legacy。
- `legacy`：永遠輸出到來源目錄下的 `formatted/`，除非明確指定 `--output-dir`。
- `sidecar`：永遠輸出到 sibling polished 目錄，除非明確指定 `--output-dir`。

## 4. CLI 變更規格

### 4.1 `--layout auto|legacy|sidecar`

預設：`auto`。

推導範例：

```text
Meeting.transcript -> Meeting.polished
Meeting.raw-transcript -> Meeting.raw-transcript.polished
transcript --layout sidecar -> transcript.polished
transcript --layout auto -> transcript/formatted
```

### 4.2 `--output-dir PATH`

既有參數保留。若使用者明確指定 `--output-dir`，它必須優先於 `--layout` 推導。

範例：

```bash
transcript-polish --dir ./Meeting.transcript --output-dir ./custom-output
```

此時不得再自動推導 `Meeting.polished/`。

### 4.3 `--meta-output PATH`

新增參數，用於指定 summary、environment、failed list 等非正文輸出位置。

預設規則：

- `layout=sidecar`，或 `layout=auto` 且命中 `*.transcript` 時，預設為 `SOURCE_PARENT/SOURCE_STEM.meta`。
- `layout=legacy` 時，可為相容繼續寫在 output dir；但若使用者指定 `--meta-output`，必須移出。

### 4.4 `--no-meta`

選擇性參數。停用 metadata 檔案輸出。整合流程不建議使用。

### 4.5 `--include-control-files`

預設目錄模式應跳過 control files。若使用者確定要處理 `_xxx.txt` 或其他控制檔，可用此參數覆蓋。

## 5. 輸入掃描規則

### 5.1 支援副檔名

維持現有：

```text
.txt
.md
```

### 5.2 預設排除規則

目錄模式預設排除：

- 檔名以 `.` 開頭。
- 檔名以 `_` 開頭，除非指定 `--include-control-files`。
- 已知控制檔名：
  - `_run-summary.txt`
  - `_environment.txt`
  - `_failed-files.txt`
  - `transcribe-run-summary.txt`
  - `transcribe-environment.txt`
  - `transcribe-failed-files.txt`
  - `polish-run-summary.txt`
  - `polish-environment.txt`
  - `polish-failed-files.txt`
- 位於輸出目錄內的檔案。
- 位於 metadata 目錄內的檔案。

建議實作方向：

```python
if path.name.startswith("."):
    return True
if path.name.startswith("_") and not include_control_files:
    return True
if path.name in KNOWN_CONTROL_FILE_NAMES and not include_control_files:
    return True
```

### 5.3 單檔模式

`--file` 模式若使用者明確指定 `_xxx.txt`，可允許處理，因為這是顯式意圖。目錄模式則應預設保護使用者，避免誤處理控制檔。

## 6. 輸出路徑推導規則

### 6.1 `*.transcript` 推導

輸入：

```text
/mnt/d/Videos/Meeting.transcript
```

推導：

```text
base_name=Meeting
output_dir=/mnt/d/Videos/Meeting.polished
meta_dir=/mnt/d/Videos/Meeting.meta
```

### 6.2 非 `*.transcript` 的 sidecar 推導

輸入：

```text
/mnt/d/Videos/RawText
```

在 `--layout sidecar` 下推導：

```text
output_dir=/mnt/d/Videos/RawText.polished
meta_dir=/mnt/d/Videos/RawText.meta
```

### 6.3 防呆規則

必須報錯：

- `output_dir` 等於 `input_dir`。
- `meta_dir` 等於 `input_dir`。
- `meta_dir` 等於 `output_dir`，除非 legacy 相容模式明確允許。
- `output_dir` 位於 `input_dir` 內，而 layout 為 sidecar。
- `input_dir` 位於 `output_dir` 內。

legacy 模式可暫時允許 `input_dir/formatted`，但 sidecar 模式不應產生巢狀輸出。

## 7. Metadata 規格

sidecar layout 下 metadata 檔名使用工具前綴：

```text
polish-run-summary.txt
polish-environment.txt
polish-failed-files.txt
```

failed list 建議格式：

```text
input_file	output_file	reason
bad.txt	bad.md	model_output_too_short
```

legacy layout 可暫時保留：

```text
formatted/_run-summary.txt
formatted/_environment.txt
```

但若使用者提供 `--meta-output`，應改寫到指定 metadata 目錄。

## 8. 與 transcribe-audio 的整合契約

`transcript-polish` 應能直接消費：

```text
Meeting.transcript/
  a.txt
  b.txt

Meeting.meta/
  transcribe-run-summary.txt
  transcribe-environment.txt
  extracted-audio.tsv
```

執行：

```bash
transcript-polish --dir ./Meeting.transcript
```

預期產生：

```text
Meeting.polished/
  a.md
  b.md

Meeting.meta/
  transcribe-run-summary.txt
  transcribe-environment.txt
  extracted-audio.tsv
  polish-run-summary.txt
  polish-environment.txt
  polish-failed-files.txt
```

完成時建議 stdout 末尾加入：

```text
[result] output_dir=/mnt/d/Videos/Meeting.polished
[result] meta_dir=/mnt/d/Videos/Meeting.meta
```

## 9. 非目標

本 CR 不改變：

- conservative polishing 原則。
- standard / quality mode 對應模型。
- OpenCC 簡轉繁行為。
- repair pass 判斷邏輯。
- prompt config、style guide、replace dict 的語意。

除非輸入掃描與輸出路徑需要，否則不應動到模型推論核心。

## 10. 測試案例

### 10.1 整合流程基本案例

輸入：

```text
Meeting.transcript/
  a.txt
  b.txt
```

執行：

```bash
transcript-polish --dir ./Meeting.transcript
```

預期：

```text
Meeting.polished/
  a.md
  b.md

Meeting.meta/
  polish-run-summary.txt
  polish-environment.txt
```

且不得產生：

```text
Meeting.transcript/formatted/
```

### 10.2 排除上游 metadata

輸入：

```text
Meeting.transcript/
  a.txt
  _run-summary.txt
  _environment.txt
  _failed-files.txt
```

預期：

- 只處理 `a.txt`。
- 不處理任何 `_*.txt`。
- summary 中應能看出實際處理數量；可另行記錄 ignored count。

### 10.3 一般 legacy 使用

輸入：

```text
transcript/
  a.txt
```

執行：

```bash
transcript-polish --dir ./transcript
```

若 `--layout auto` 且目錄名不是 `*.transcript`，預期保留：

```text
transcript/formatted/a.md
```

### 10.4 強制 sidecar

```bash
transcript-polish --dir ./transcript --layout sidecar
```

預期：

```text
transcript.polished/a.md
transcript.meta/polish-run-summary.txt
```

### 10.5 明確指定 output 與 meta

```bash
transcript-polish --dir ./Meeting.transcript \
  --output-dir /tmp/polished \
  --meta-output /tmp/meta
```

預期：

- 輸出 markdown 至 `/tmp/polished`。
- 寫入 metadata 至 `/tmp/meta`。
- 不自動產生 `Meeting.polished/` 或 `Meeting.meta/`。

## 11. 實作順序建議

1. 將 input discovery 的排除規則從列舉 `_run-summary.txt`、`_environment.txt` 改為通用 control file skip。
2. 新增 `--include-control-files`。
3. 新增 `--layout auto|legacy|sidecar`，先實作 output dir 推導，不動模型流程。
4. 新增 `--meta-output` 與 sidecar metadata 檔名。
5. 新增 failed list 輸出。
6. 更新 README、INSTALL 與既有 SDD 文件中的目錄範例。
7. 新增 path resolution 與 input discovery 單元測試。

## 12. 驗收標準

完成後，以下兩個指令應可自然串接：

```bash
transcribe-audio ./Meeting
transcript-polish --dir ./Meeting.transcript
```

目標輸出：

```text
Meeting/
Meeting.transcript/
Meeting.polished/
Meeting.meta/
```

並且：

- `Meeting.transcript/` 中的 `_*.txt` 不會被目錄模式處理。
- `Meeting.polished/` 只包含潤稿後 Markdown 正文。
- `Meeting.meta/` 包含上游與本工具的 summary、environment、failed list。
- 一般 `transcript-polish --dir ./transcript` 仍可保留既有 `formatted/` 行為。
- 使用者可用 `--layout sidecar` 強制 sidecar，也可用 `--layout legacy` 強制舊行為。
