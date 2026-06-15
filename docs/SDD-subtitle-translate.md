# SDD: subtitle-translate

最後更新：2026-06-16  
狀態：Draft

## 1. 產品目標

`subtitle-translate` 是與 `transcript-polish` 安裝在同一個 Python package 中的獨立 CLI。

它的固定定位是：

> 使用本機 LLM 翻譯 SRT 字幕文字，保留原始字幕編號、順序與時間軸，輸出可直接交由字幕軟體校正的目標語言 SRT。

第一個正式驗收情境為：

```text
中文或英文 SRT -> 日文 SRT
```

本工具只處理已存在的字幕檔，不執行 WhisperX，也不直接修改或燒錄影片。

## 2. 與 transcript-polish 的關係

兩支工具位於同一個 repository、distribution、Python package 與虛擬環境：

```text
repository: michaelpo99/transcript-polish
distribution: transcript-polish
package: transcript_polish
venv: ~/.venvs/transcript-polish/
```

安裝後提供：

```text
transcript-polish      整理 TXT／Markdown 逐字稿
subtitle-translate     翻譯 SRT 字幕
```

兩者共用：

- Standard／Quality mode。
- Qwen 模型載入。
- CUDA 與量化環境檢查。
- token budget 與生成服務。
- 使用者預設 mode。
- 執行摘要與環境資訊。

兩者不得共用：

- prompt。
- 輸入 parser。
- 輸出檔名規則。
- 結果驗證。
- OpenCC 正規化。
- repair／retry 判斷。

共用核心的重構規格見 `SDD-shared-runtime-refactor.md`。

## 3. 產品邊界

### 3.1 可以做

1. 讀取單一 SRT 或批次掃描目錄第一層的 SRT。
2. 使用上下文將字幕翻譯成日文。
3. 保留 cue 編號、順序與時間軸。
4. 保留 URL、路徑、指令、程式碼、版本號、數字與專有名詞。
5. 透過 glossary 提供術語、人名與產品名稱的固定翻譯。
6. 驗證模型輸出，避免漏譯、增加 cue 或破壞 SRT 結構。
7. 產生執行摘要、環境資訊與失敗紀錄。

### 3.2 不應做

1. 不執行語音辨識。
2. 不修正影片時間軸。
3. 不自動合併或拆分 cue。
4. 不改變 cue 的開始與結束時間。
5. 不摘要、濃縮或補充原文沒有的資訊。
6. 不把字幕改寫成文章。
7. 不直接把字幕燒進影片。
8. 不以 OpenCC 處理日文輸出。
9. 不直接讓模型重寫完整 SRT 格式。
10. 第一版不產生雙語字幕。

## 4. CLI 規格

### 4.1 基本用法

```bash
subtitle-translate --file <path> --target-language ja
subtitle-translate --dir <path> --target-language ja
```

日文為第一版預設目標語言，因此可省略：

```bash
subtitle-translate --file lesson.zh.srt
subtitle-translate --dir ./transcript
```

### 4.2 建議參數

```text
--file <path>
    處理單一 .srt。

--dir <path>
    處理指定目錄第一層的 .srt，不遞迴。

--source-language <code>
    原文語言，預設 auto。
    第一版正式驗收 zh、en；auto 由 prompt 與內容判斷。

--target-language <code>
    目標語言，預設 ja。
    第一版只保證 ja 的品質與測試。

--mode <standard|quality>
    沿用共用 mode。

--model <hugging-face-model>
    明確指定模型，優先於 mode。

--quantization <none|4bit>
    明確指定量化方式，優先於 mode。

--glossary <path>
    載入來源詞彙到目標詞彙的術語表。

--style-guide <path>
    載入本次翻譯的附加語氣與術語指引。

--prompt-config <path>
    載入字幕翻譯專用 prompt 設定。

--output-dir <name-or-path>
    輸出子目錄或絕對路徑，預設 translated。

--batch-size <N>
    每批最多翻譯的 active cues 數量。
    預設值由實測決定，建議起始值為 20。

--context-cues <N>
    每批前後提供但不要求輸出的 context cues 數量。
    預設 2。

--force
    覆蓋已存在的輸出檔。

--verbose
    顯示批次、retry 與驗證資訊。
```

### 4.3 參數限制

1. `--file` 與 `--dir` 不可同時指定。
2. `--batch-size` 必須大於 0。
3. `--context-cues` 不得小於 0。
4. 輸出目錄不可與輸入 base directory 相同。
5. 來源與目標檔案不得解析成同一路徑。
6. 不支援的副檔名應在載入模型前報錯。

## 5. 輸入與輸出

### 5.1 輸入

第一版只支援 UTF-8／UTF-8 BOM 的 `.srt`。

每個 cue 至少包含：

```text
cue id
time range
text
```

例如：

```srt
41
00:02:10,500 --> 00:02:13,800
這個需要先把它開起來。

42
00:02:14,100 --> 00:02:17,000
然後再執行剛才那一支。
```

### 5.2 SRT parser

parser 必須：

1. 保留 cue 原始 ID。
2. 保留原始時間行字串，不重新格式化。
3. 保留 cue 順序。
4. 支援 cue 文字多行。
5. 容許 CRLF 或 LF。
6. 在格式錯誤時回報 cue 或行號。
7. 不因 ID 非連續就自動重新編號。
8. 不因時間重疊就自動修正。

內部資料模型建議：

```python
@dataclass(frozen=True)
class SubtitleCue:
    cue_id: str
    timing_line: str
    text: str
    source_index: int
```

`cue_id` 使用字串保存，避免 parser 自動正規化原始內容。

### 5.3 輸出目錄

預設：

```text
<input-base>/translated/
```

### 5.4 輸出檔名

規則：

1. 若輸入 stem 以明確來源語言 suffix 結尾，替換為目標語言。
2. 否則在副檔名前附加目標語言。

例如：

```text
lesson.srt       -> lesson.ja.srt
lesson.zh.srt    -> lesson.ja.srt
lesson.en.srt    -> lesson.ja.srt
lesson.part1.srt -> lesson.part1.ja.srt
```

只有當末段完全等於已知來源語言 code 時才替換，不得誤改一般檔名。

### 5.5 原子寫入

每個輸出檔必須先寫入同目錄暫存檔：

```text
.<filename>.part
```

僅在全部 cue 翻譯與驗證成功後才 rename 成正式檔案。

任一批次最後失敗時：

- 不得留下部分完成的正式 SRT。
- 應刪除暫存檔。
- 應將檔案及失敗原因記錄到 `_failed-files.txt`。

## 6. 模型策略

### 6.1 第一版模型

沿用現有模式：

| 模式 | 模型 | 定位 |
| --- | --- | --- |
| `standard` | `Qwen/Qwen2.5-3B-Instruct`、無量化 | 測試、速度優先 |
| `quality` | `Qwen/Qwen2.5-7B-Instruct`、4-bit | 正式翻譯、品質優先 |

第一版不要求新增 TranslateGemma、NLLB 或其他翻譯模型。

### 6.2 預設建議

CLI 與使用者設定仍可維持 `standard` 預設，以保持既有安裝相容；文件應明確建議正式字幕使用：

```bash
subtitle-translate --mode quality ...
```

### 6.3 模型載入次數

單次執行無論處理幾個檔案，模型只載入一次。

若所有檔案皆 skipped 或 preflight 失敗，不得載入模型。

## 7. 翻譯流程

完整流程：

```text
掃描輸入
  -> preflight 與輸出衝突檢查
  -> 解析 SRT
  -> 保護不可翻譯 token
  -> 建立 batches 與 context
  -> 模型翻譯 active cues
  -> 解析 JSON 回應
  -> 結構與內容驗證
  -> 必要時 retry／縮小 batch
  -> 還原 protected tokens
  -> 寫回原始 timing 與 cue id
  -> 原子輸出 SRT
  -> 寫執行摘要
```

### 7.1 不得把完整 SRT 交給模型重寫

模型只接收 cue ID 與文字，不接收可修改的正式 timing line。

程式自行保存並重建 SRT：

```text
原始 cue id      程式保存
原始 timing line 程式保存
翻譯文字         模型產生
SRT 結構          程式重建
```

這是避免時間軸損壞的核心設計。

## 8. Batch 與上下文策略

### 8.1 Active cues

每批選定一組需要翻譯的 active cues，例如 20 條。

模型必須只回傳 active cue IDs。

### 8.2 Context cues

為改善代名詞、主詞省略與術語一致性，可在 active batch 前後提供少量唯讀 context cues。

例如：

```text
context_before: 2 cues
active:         20 cues
context_after:  2 cues
```

context cues：

- 只供理解。
- 不得出現在回傳結果。
- 已翻譯的前文可同時提供原文與已確認譯文。
- 尚未翻譯的後文只提供原文。

### 8.3 Token budget

`--batch-size` 是最大 cue 數，不代表一定一次送滿。

batcher 必須同時考慮：

- system prompt。
- glossary。
- style guide。
- context cues。
- active cue 文字。
- 預留輸出 token。
- safety margin。

若超過安全預算，應減少 active cues；單一 cue 仍超過上限時應明確報錯。

### 8.4 不跨檔案批次

第一版每個 batch 只包含同一個 SRT 的 cues，不跨檔案合併，避免上下文污染與失敗回復複雜化。

## 9. 模型輸入與輸出契約

### 9.1 建議輸入格式

程式將 active cues 組成 JSON：

```json
{
  "source_language": "zh",
  "target_language": "ja",
  "context_before": [
    {"id": "39", "source": "先確認環境變數。"}
  ],
  "items": [
    {"id": "41", "source": "這個需要先把它開起來。"},
    {"id": "42", "source": "然後再執行剛才那一支。"}
  ],
  "context_after": [
    {"id": "43", "source": "執行完成後會看到輸出目錄。"}
  ]
}
```

### 9.2 模型回應格式

模型只能回傳 active items：

```json
{
  "items": [
    {"id": "41", "translation": "まず、これを起動しておく必要があります。"},
    {"id": "42", "translation": "その後、先ほどのスクリプトを実行します。"}
  ]
}
```

不得要求模型輸出 Markdown code fence、SRT timing 或說明文字。

### 9.3 JSON 解析

parser 應：

1. 先嘗試解析完整回應為 JSON object。
2. 可容許模型誤加單層 Markdown code fence並清除。
3. 不應以寬鬆 regex 猜測大量破損內容。
4. 無法可靠解析時進入 retry，不得直接採用。

## 10. Prompt 規格

### 10.1 核心翻譯原則

字幕翻譯 prompt 必須要求：

1. 忠實翻譯，不摘要、不補充、不解釋。
2. 翻成自然且適合字幕閱讀的日文。
3. 依上下文處理省略主詞、代名詞與語氣。
4. 保留產品名、函式名、CLI 指令、路徑、URL、版本號與程式碼。
5. 遵守 glossary 指定譯法。
6. 不翻譯 protected token。
7. 不增加或刪除 active cue。
8. 不合併、拆分或重新排序 ID。
9. 只輸出指定 JSON schema。
10. 不輸出翻譯說明、註解或替代版本。

### 10.2 日文風格

第一版預設：

- 使用自然、清楚的現代日文。
- 教學影片預設採中性禮貌體，以 `です／ます` 為主。
- 不擅自增加敬稱。
- 不把技術詞彙過度意譯。
- 原文口氣明顯輕鬆時，可以保留較口語的日文，但仍應一致。

style guide 可以覆蓋語氣偏好，但不得覆蓋結構保護與忠實原則。

### 10.3 Prompt config

字幕 prompt config 應與逐字稿 prompt config 分開，至少包含：

```json
{
  "system_prompt": "...",
  "repair_prompt": "...",
  "user_instruction": "...",
  "repair_user_instruction": "..."
}
```

不得直接沿用 `transcript-polish` 的繁體中文整理 prompt。

## 11. Glossary

### 11.1 格式

第一版建議沿用簡單文字格式：

```text
來源詞 => 目標詞
```

例如：

```text
虛擬環境 => 仮想環境
逐字稿 => 文字起こし
WhisperX => WhisperX
Codex => Codex
```

規則：

1. 忽略空白行。
2. 忽略 `#` 開頭註解。
3. 格式錯誤需回報行號。
4. 同一來源詞重複定義時報錯。
5. glossary 是翻譯指引，不是翻譯完成後的盲目全域字串替換。

### 11.2 適用範圍

只將與當前 batch 內容相關的 glossary 項目放入 prompt，避免詞彙表過大占用 context。

匹配可以先採簡單 case-sensitive／case-insensitive 規則；對中日文不做斷詞依賴。

## 12. Protected tokens

下列內容原則上不得被模型翻譯或改寫：

- URL。
- email。
- Windows／Linux 路徑。
- CLI 指令片段。
- 版本號。
- 純數字與時間。
- SRT／HTML 標記。
- ASS 類 inline tag，例如 `{\an8}`。

程式可在送模型前替換為 placeholder：

```text
__PROTECTED_0001__
```

翻譯後必須：

1. placeholder 集合完全一致。
2. 不可遺失、重複或增加 placeholder。
3. 還原原始 token。
4. 驗證還原後內容。

若 placeholder 驗證失敗，該 batch 不得採用。

## 13. Cue 邊界與換行

第一版固定保留 cue 邊界：

- 不合併 cue。
- 不拆分 cue。
- 不改時間。
- cue 數量不變。

同一 cue 內的換行不是時間軸的一部分。第一版可允許譯文重新換行，但必須維持在同一 cue 中。

字幕最佳行寬、每秒字數、重新切 cue 與 retiming 屬於後續字幕排版功能，不納入第一版翻譯驗收。

## 14. 驗證規則

每個 batch 至少檢查：

1. 回傳 JSON 可解析。
2. 回傳 `items` 為 list。
3. active cue ID 集合完全相同。
4. ID 不重複。
5. 沒有 context cue ID。
6. 每個 translation 為非空字串。
7. protected placeholders 完全一致。
8. 不含明顯 wrapper，例如「以下是翻譯結果」。
9. 不含模型說明或 Markdown code fence。

檔案完成後至少檢查：

1. cue 數量不變。
2. cue ID 順序不變。
3. timing line 逐字相同。
4. 每個 cue 都有譯文。
5. 輸出可由本專案 SRT parser 再次讀取。

### 14.1 只警告、不直接判失敗的檢查

以下情況可能合理，第一版只記錄 warning：

- 譯文與原文相同，例如產品名或程式碼。
- 譯文長度明顯比原文長或短。
- cue 內仍含少量來源語言文字。
- 日文中包含必要英文術語。

這些指標應寫入 summary，供人工抽查，但不得用單純比例直接否決有效翻譯。

## 15. Retry 與失敗策略

### 15.1 第一次 retry

若模型回應無法解析或結構驗證失敗，使用 repair prompt 重送同一 batch，並附上：

- 原始 active items。
- 上次無效回應。
- 明確的驗證錯誤。
- 正確 JSON schema。

### 15.2 縮小 batch

repair 仍失敗時：

1. 將 active batch 對半拆分。
2. 個別重試。
3. 直到單一 cue。

### 15.3 最終失敗

單一 cue 仍失敗時：

- 將整個輸入檔標記為失敗。
- 不輸出不完整正式 SRT。
- `_failed-files.txt` 記錄檔名、cue ID、錯誤類型與最後訊息。

第一版不以原文自動填補失敗譯文，避免產生看似成功但實際漏譯的字幕。

## 16. 執行輸出與報表

預設輸出目錄：

```text
translated/
├── lesson.ja.srt
├── _run-summary.txt
├── _environment.txt
└── _failed-files.txt   # 有失敗時才建立
```

### 16.1 `_environment.txt`

至少包含：

```text
command=subtitle-translate
python_version=
transformers_version=
torch_version=
cuda_available=
cuda_runtime=
gpu_name=
gpu_vram_mb=
mode=
mode_source=
model=
quantization=
source_language=
target_language=
batch_size=
context_cues=
```

### 16.2 `_run-summary.txt`

至少包含：

```text
source=
output_dir=
started_at=
finished_at=
files_found=
files_queued=
files_success=
files_failed=
files_skipped=
cue_count=
translated_cue_count=
batch_count=
retry_count=
batch_split_count=
warning_count=
```

## 17. 效能與資源

1. 模型只載入一次。
2. 檔案依序處理，第一版不平行執行多個 GPU inference。
3. batch 依 token budget 動態縮小。
4. 已存在輸出預設 skipped。
5. 長影片不應把全部字幕一次送入模型。
6. glossary 只注入相關詞彙。
7. RuntimeInfo 與 preflight 應在模型載入前完成。

## 18. 安全與隱私

第一版只使用本機 Hugging Face 模型：

- 不將字幕送到外部 API。
- 不需要雲端金鑰。
- 執行報表不得寫入完整字幕內容。
- 錯誤檔案可以記錄 cue ID 與錯誤原因，但避免寫出大段原文或譯文。

## 19. 與 extract-audio 的整合方式

典型流程：

```bash
transcribe-audio \
  --language zh \
  --output-format srt \
  /path/to/videos

subtitle-translate \
  --dir /path/to/videos/transcript \
  --source-language zh \
  --target-language ja \
  --mode quality
```

輸出：

```text
/path/to/videos/transcript/translated/*.ja.srt
```

兩個 repository 先維持鬆耦合：

- `extract-audio` 只負責媒體抽音與 ASR。
- `transcript-polish` package 負責文字整理與字幕翻譯。
- 第一版不要求由 `transcribe-audio` 自動呼叫 `subtitle-translate`。

## 20. 測試規格

建議新增：

```text
tests/subtitle/test_srt_parser.py
tests/subtitle/test_output_paths.py
tests/subtitle/test_batching.py
tests/subtitle/test_prompt_contract.py
tests/subtitle/test_response_parser.py
tests/subtitle/test_validation.py
tests/subtitle/test_retry.py
tests/subtitle/test_cli_preflight.py
tests/subtitle/test_workflow.py
tests/subtitle/test_reporting.py
```

### 20.1 Parser 案例

1. 標準 SRT。
2. CRLF／LF。
3. UTF-8 BOM。
4. 多行 cue。
5. cue ID 不連續。
6. timing line 含 positioning metadata。
7. cue 空文字。
8. 格式錯誤行號。

### 20.2 模型回應案例

1. 正確 JSON。
2. 外包 Markdown code fence。
3. 漏 ID。
4. 多 ID。
5. ID 重複。
6. 回傳 context ID。
7. translation 空白。
8. placeholder 遺失。
9. wrapper 說明文字。
10. JSON 截斷。

### 20.3 Workflow 案例

1. 全 skipped 不載模型。
2. 多檔只載入一次模型。
3. batch 超過 token budget 時縮小。
4. repair 成功。
5. repair 失敗後 batch split。
6. 單一 cue 最終失敗時不留下正式輸出。
7. 完成後 cue ID 與 timing 逐字一致。
8. glossary 只注入相關詞彙。
9. OpenCC 不在字幕 workflow 中執行。
10. `standard` 與 `quality` 共用相同 entrypoint 基礎設施。

## 21. P0 實作範圍

第一版必須完成：

1. 新增 `subtitle-translate` entry point。
2. 支援單檔與目錄第一層 `.srt`。
3. 預設翻成日文。
4. 使用 Qwen 3B／7B 現有模式。
5. SRT parser 與 serializer。
6. 動態 batch 與少量 context。
7. JSON 輸出契約。
8. 結構驗證。
9. repair 與 batch split。
10. glossary。
11. protected token。
12. 原子輸出。
13. summary、environment、failed-files。
14. 對應單元測試與最小整合測試。

## 22. P1 候選功能

第一版完成後再評估：

1. `.vtt`。
2. 中日雙語字幕。
3. 字幕行寬與換行排版。
4. 每秒字數與閱讀速度警告。
5. cue 合併、拆分與 retiming。
6. 字幕校正模式，只修正原文、不翻譯。
7. TranslateGemma、NLLB、GGUF、Ollama 或 llama.cpp 後端。
8. checkpoint／resume。
9. 與 `transcribe-audio` 的一鍵串接。
10. 翻譯品質抽樣報告。

## 23. 非目標

第一版不包含：

1. GUI。
2. 影片播放器。
3. 影片燒錄。
4. 雲端翻譯 API。
5. 語者辨識。
6. 自動辨識人名。
7. 摘要或會議紀錄。
8. repository 或 package 改名。

## 24. 驗收條件

第一版可視為完成，至少需符合：

1. 同一安裝環境可執行 `transcript-polish` 與 `subtitle-translate`。
2. 中文與英文 SRT 可翻成日文 SRT。
3. 輸出 cue 數量、ID 順序與 timing line 與原檔完全一致。
4. 模型不能新增、刪除、合併或拆分 cue。
5. 正式輸出不含 JSON、Markdown wrapper 或模型說明。
6. glossary 指定詞彙能穩定套用。
7. URL、指令、路徑與版本號不被破壞。
8. 無效模型輸出會 retry，最終失敗不產生不完整正式檔。
9. 全 skipped 時不載入模型。
10. `transcript-polish` 原有行為與測試不因新增功能而退化。

正式字幕的優先順序為：

```text
結構與時間軸安全 > 忠實度 > 術語一致 > 日文自然度 > 文體美化
```
