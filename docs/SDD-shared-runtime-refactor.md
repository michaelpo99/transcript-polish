# SDD: 共用模型執行核心與雙 CLI 重構

最後更新：2026-06-16  
狀態：Draft

## 1. 目的

本文件定義 `transcript-polish` repository 在加入字幕翻譯功能前，既有程式需要進行的結構調整。

重構完成後，同一個 Python distribution 與 package 應提供兩支獨立 CLI：

```text
transcript-polish
subtitle-translate
```

兩支 CLI：

1. 共用模型選擇、模型載入、推論、CUDA／量化檢查、token 預算與執行報表。
2. 各自擁有獨立的參數解析、prompt、輸入格式、驗證規則與 workflow。
3. 不得透過 monkey patch 修改另一個 CLI 模組中的函式。
4. 不改變既有 `transcript-polish` 的產品定位與預設行為。

## 2. 背景與現況問題

目前 `transcript-polish` 已具備：

- Qwen 3B／7B 模式。
- CUDA 與 4-bit 量化檢查。
- 本機模型載入與文字生成。
- 使用者預設 mode。
- `_run-summary.txt` 與 `_environment.txt`。
- prompt token 預算與輸出檢查。

但目前 `entrypoint.py` 為了加入 mode，會暫時替換 `cli.build_parser`、`cli.print_run_config`、`cli.write_summary_files` 與 `cli.generate_response`，執行後再還原。

這種做法在單一 CLI 下可以運作，但加入第二個 CLI 後會產生以下問題：

1. 共用功能難以重用，只能複製或再次 monkey patch。
2. 單元測試容易受到全域函式替換影響。
3. 入口層與業務層耦合，無法清楚辨識功能邊界。
4. 未來增加其他模型後端或工作流程時，修改範圍會持續擴大。

## 3. 設計原則

### 3.1 保持相容

重構後，下列既有操作必須維持相容：

```bash
transcript-polish --file <path>
transcript-polish --dir <path>
transcript-polish --mode standard
transcript-polish --mode quality
transcript-polish --model <name>
transcript-polish --quantization <none|4bit>
```

既有預設值、輸出目錄、檔名、prompt 行為、替換詞彙表與使用者設定檔語意不得因重構而改變。

### 3.2 共用基礎設施，不共用業務流程

應共用：

- mode preset 與優先順序。
- 使用者設定讀取。
- RuntimeInfo 與環境檢查。
- 模型載入。
- 推論與 token budget。
- 共通錯誤型別。
- 執行摘要與環境資訊寫入。

不應共用：

- CLI parser。
- 輸入檔案解析。
- prompt 內容。
- 輸出檔名策略。
- 結果驗證。
- retry 規則。
- OpenCC 或其他特定文字正規化。

### 3.3 依賴方向

依賴只能由 CLI／workflow 指向共用核心：

```text
polish CLI ───────┐
                  ├──> common runtime / model / generation / reporting
subtitle CLI ─────┘
```

共用核心不得反向匯入 `polish` 或 `subtitle` workflow。

## 4. 目標專案結構

第一階段建議結構：

```text
src/transcript_polish/
├── __init__.py
├── common/
│   ├── __init__.py
│   ├── errors.py
│   ├── mode.py
│   ├── runtime.py
│   ├── model_loader.py
│   ├── generation.py
│   ├── token_budget.py
│   └── reporting.py
├── polish/
│   ├── __init__.py
│   ├── cli.py
│   ├── workflow.py
│   ├── prompts.py
│   ├── normalization.py
│   └── validation.py
├── subtitle/
│   ├── __init__.py
│   ├── cli.py
│   ├── workflow.py
│   ├── prompts.py
│   ├── srt.py
│   ├── batching.py
│   └── validation.py
├── polish_entrypoint.py
└── subtitle_entrypoint.py
```

不要求一次把所有現有函式移到上述最終位置；可以分階段搬移，但不得建立第二套模型載入與 mode 處理實作。

## 5. CLI entry point

`pyproject.toml` 應調整為：

```toml
[project.scripts]
transcript-polish = "transcript_polish.polish_entrypoint:main"
subtitle-translate = "transcript_polish.subtitle_entrypoint:main"
```

### 5.1 entrypoint 責任

每個 entrypoint 只負責：

1. 取得 argv。
2. 呼叫該 CLI 的 parser。
3. 解析共用 mode／model selection。
4. 呼叫該 workflow。
5. 將 `UserFacingError` 轉成終端錯誤訊息與 exit code。

entrypoint 不應：

- 修改其他模組的全域函式。
- 實作檔案掃描。
- 組 prompt。
- 直接處理模型輸出。

## 6. 共用 mode 與模型選擇

### 6.1 ModePreset

共用模組應保留：

```text
standard -> Qwen/Qwen2.5-3B-Instruct, quantization=none
quality  -> Qwen/Qwen2.5-7B-Instruct, quantization=4bit
```

### 6.2 優先順序

模型與量化設定優先順序維持：

```text
CLI 明確指定 --model / --quantization
> CLI --mode
> 使用者設定檔 mode
> 內建 standard
```

### 6.3 Quality fallback

若 `quality` 來自使用者設定檔，但環境缺少 CUDA、`accelerate` 或 `bitsandbytes`，可以自動退回 `standard`。

若使用者在本次 CLI 明確指定 `--mode quality`，環境不符時應報錯，不得靜默退回。

### 6.4 使用者設定檔

第一版兩支 CLI 共用：

```text
~/.config/transcript-polish/config.toml
```

第一版只使用：

```toml
mode = "quality"
```

未來若有必要，可擴充為：

```toml
[defaults]
mode = "quality"

[subtitle]
target_language = "ja"
```

本輪不要求實作命令專屬設定。

## 7. 共用 RuntimeInfo

RuntimeInfo 至少包含：

- Python 版本。
- Torch 版本。
- Transformers 版本。
- Accelerate 版本。
- BitsAndBytes 版本。
- CUDA 是否可用。
- CUDA runtime。
- GPU 名稱。
- GPU VRAM。
- import／環境錯誤。

RuntimeInfo 應只檢查環境，不應載入完整模型。

在所有工作皆 skipped、輸入不存在、輸出衝突或 CLI 參數錯誤時，不得載入模型。

## 8. 共用模型載入與推論

### 8.1 ModelLoader

模型載入函式輸入：

```text
model_name
quantization
auto device policy
```

輸出統一的 LoadedModel，至少包含：

- tokenizer。
- model。
- input device。
- dtype。
- quantization。
- memory footprint。

### 8.2 Generation service

共用 generation service 負責：

1. 套用 chat template。
2. 計算 prompt token。
3. 驗證 context budget。
4. 執行 `generate()`。
5. 截取新生成 token。
6. decode。
7. 檢查空輸出與基礎生成錯誤。

它不得自行清理 Markdown wrapper、解析 JSON 或判斷字幕 ID；這些屬於各 workflow。

### 8.3 參數可配置

共用 generation API 至少接受：

```text
max_new_tokens
do_sample
temperature
top_p
```

既有 `transcript-polish` 應維持現有 deterministic 行為。字幕翻譯第一版亦應以 deterministic 為預設。

## 9. 執行報表

兩支 CLI 均輸出：

```text
_run-summary.txt
_environment.txt
```

共通欄位：

```text
command
mode
mode_source
model
quantization
python_version
torch_version
transformers_version
cuda_available
gpu_name
gpu_vram_mb
started_at
finished_at
success_count
failed_count
skipped_count
```

命令專屬欄位由 workflow 增加，例如：

```text
source_language
target_language
subtitle_count
translated_cue_count
retry_count
```

報表模組應接受 key-value mapping，不應硬編碼特定 workflow 的所有欄位。

## 10. 錯誤處理

共用核心應定義一個對使用者友善的錯誤型別，例如：

```python
class UserFacingError(Exception):
    pass
```

程式內部錯誤應保留原始 exception chain；CLI 最外層只輸出必要訊息。

exit code 建議：

```text
0 成功，包含全部 skipped
1 執行失敗或部分檔案失敗
2 CLI 參數錯誤
```

若現有 CLI 已有不同慣例，重構第一階段優先維持相容，exit code 統一可另列後續工作。

## 11. 相容性與遷移策略

### Phase 1：抽共用 mode 與 runtime

1. 將 ModePreset、ModeSelection、RuntimeInfo 與使用者設定讀取抽出。
2. 保留原 CLI 對外介面。
3. 建立回歸測試，確認現有行為不變。

### Phase 2：抽模型載入與 generation

1. 將模型載入移到共用模組。
2. 將 token budget 與生成流程移到共用模組。
3. 原 polish workflow 改由明確依賴注入呼叫共用服務。
4. 移除 entrypoint monkey patch。

### Phase 3：建立第二個 entry point

1. 在 `pyproject.toml` 增加 `subtitle-translate`。
2. 建立 subtitle package 與最小 CLI。
3. 實作字幕 workflow，內容見 `SDD-subtitle-translate.md`。

### Phase 4：清理相容層

1. 舊 `cli.py` 若仍存在，只保留轉呼叫或在下一個 major version 移除。
2. 更新 README、INSTALL 與測試文件。

## 12. 測試要求

重構至少新增或保留以下測試：

```text
tests/test_mode_selection.py
tests/test_runtime_detection.py
tests/test_model_loading.py
tests/test_generation_budget.py
tests/test_polish_cli_compatibility.py
tests/test_entrypoints.py
```

必要案例：

1. 既有 `transcript-polish --help` 參數不消失。
2. `standard`／`quality` 映射不變。
3. 明確指定 model 的優先權不變。
4. 使用者設定 quality 在不支援環境下退回 standard。
5. CLI 明確指定 quality 時不應靜默退回。
6. 全 skipped 時不載模型。
7. 兩支 CLI 可在同一 venv 中獨立啟動。
8. 執行其中一支 CLI 不會修改另一支 CLI 的函式或全域狀態。

## 13. 非目標

本重構不包含：

1. 改用 GGUF、Ollama、LM Studio 或 llama.cpp。
2. 更換既有 Qwen 模型。
3. 將 repository 或 distribution 改名。
4. 合併逐字稿整理與字幕翻譯 prompt。
5. 新增 GUI。
6. 直接執行 WhisperX。

## 14. 驗收條件

重構可視為完成，至少需符合：

1. `transcript-polish` 原有測試全部通過。
2. 既有主要 CLI 操作與輸出結果沒有非預期差異。
3. `entrypoint.py` 不再 monkey patch `cli` 函式。
4. `subtitle-translate --help` 可由同一安裝環境執行。
5. 兩個 workflow 共用同一套 mode、runtime、model loader 與 generation service。
6. OpenCC 與逐字稿專屬邏輯沒有進入字幕翻譯 workflow。
