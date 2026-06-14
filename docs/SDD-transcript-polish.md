# SDD: 逐字稿整理 CLI 工具

最後更新：2026-06-14

## 1. 目標

設計一支 CLI 工具，掃描「當前目錄」或指定目錄中的逐字稿檔案，使用本地端 LLM 進行校正、繁體化、標點補全、分段與 Markdown 排版，並將輸出統一放到來源目錄下的 `formatted/` 子目錄。

這支工具的定位是：

1. 盡量零設定即可使用。
2. 預設行為以「掃描目前目錄第一層」為主，符合日常批次處理習慣。
3. 工具本身不執行 WhisperX，只處理 WhisperX 或其他來源已產生的文字稿。
4. 支援內建規則、外部替換詞彙表與額外 AI 指引三層整理策略。
5. 可用參數切換模型，但預設值應適合 `RTX 3080 10GB` 的本地使用情境。

建議指令名稱：

```text
bin/transcript-polish
```

若之後安裝成全域指令，建議名稱：

```text
transcript-polish
```

---

## 2. 使用情境

### 2.1 主要情境

使用者在某個資料夾中已有逐字稿，例如：

```text
episode-01.txt
episode-02.txt
episode-03.md
```

執行：

```bash
./bin/transcript-polish
```

工具自動：

1. 掃描目前目錄第一層的 `.txt` 與 `.md` 檔案。
2. 排除 `formatted/` 內既有成品與明顯非輸入用途檔案。
3. 載入內建替換規則。
4. 使用預設模型整理逐字稿。
5. 將輸出寫入 `./formatted/`。

### 2.2 指定單一檔案情境

執行：

```bash
./bin/transcript-polish --file ./episode-01.txt
```

工具只處理指定檔案，並將輸出寫入：

```text
./formatted/episode-01.md
```

### 2.3 指定目錄情境

執行：

```bash
./bin/transcript-polish --dir ./transcript
```

工具需：

1. 只掃描 `./transcript` 第一層。
2. 不遞迴子目錄。
3. 將輸出寫入：

```text
./transcript/formatted/
```

### 2.4 使用外部替換詞彙表情境

執行：

```bash
./bin/transcript-polish --replace-dict ./replacements.txt
```

工具需先載入外部替換表，再與內建規則一併套用到每份輸入文字後，才送入模型。

### 2.5 使用額外 AI 指引情境

執行：

```bash
./bin/transcript-polish --style-guide ./style-guide.txt
```

工具需將該檔案內容附加到 prompt，作為額外參考規則，但不得宣稱其效果等同強制替換。

### 2.6 覆蓋重跑情境

執行：

```bash
./bin/transcript-polish --force
```

若 `formatted/` 內已有同名輸出，允許覆蓋。

---

## 3. 非目標

第一版不處理以下需求：

1. 不做子目錄遞迴掃描。
2. 不保留輸入 `.md` 的原始 Markdown 結構。
3. 不讓 AI 自由解析任意格式的替換詞彙表並保證正確套用。
4. 不直接執行 WhisperX、Whisper 或其他語音辨識流程。
5. 第一輪不實作完整 chunking、overlap 與多段合併策略。

### 3.1 下一輪優先順序

本工具下一輪修正的優先順序固定如下：

1. 先修正 correctness 問題。
2. 再修正 repair 與標題等直接影響輸出品質的機制。
3. 最後才評估長文 chunking 與更進一步的品質優化。

第一輪修正範圍應聚焦於：

1. 空輸出不得記為 success。
2. 所有檔案皆為 skipped 時，不得載入模型。
3. 執行前需檢查輸出衝突。
4. `--output-dir` 相對路徑語意需統一。
5. `clean_response()` 不得用寬鬆關鍵字誤刪正文尾句。
6. repair 觸發條件不得因正常英文術語而誤判。
7. repair 採用前需做基本安全檢查。
8. 過長輸入需先做 token 長度防護。
9. 補少量高價值回歸測試。

---

## 4. CLI 規格

### 4.1 基本用法

```bash
transcript-polish
transcript-polish --file <path>
transcript-polish --dir <path>
transcript-polish --model <name>
transcript-polish --quantization <mode>
transcript-polish --replace-dict <path>
transcript-polish --style-guide <path>
transcript-polish --force
```

### 4.2 參數

```text
--file <path>
    處理單一檔案，僅接受 .txt 或 .md。

--dir <path>
    處理指定目錄第一層的 .txt 與 .md。

--model <name>
    指定 Hugging Face 模型名稱。
    預設為 Qwen/Qwen2.5-3B-Instruct。

--quantization <mode>
    指定模型載入模式。
    支援 none、4bit。
    預設為 none。

--replace-dict <path>
    載入外部強制替換詞彙表。

--style-guide <path>
    載入額外 AI 參考指引檔。

--output-dir <name-or-path>
    指定輸出子目錄名稱或路徑。
    若未指定，預設為 formatted。

-f, --force
    覆蓋已存在的輸出檔。

-h, --help
    顯示說明。
```

### 4.3 參數衝突與優先順序

```text
使用者明確指定 > 自動推定 > 內建預設值
```

規則如下：

1. `--file` 與 `--dir` 不可同時指定。
2. 若未指定 `--file` 與 `--dir`，預設掃描目前工作目錄。
3. 若指定 `--output-dir`，優先使用使用者指定值。
4. 若指定 `--model`，不得自動改用其他模型。
5. `--output-dir` 若為相對路徑，無論是一層或多層路徑，都一律相對於輸入 base directory 解譯。

---

## 5. 輸入與輸出規格

### 5.1 輸入檔案

預設支援以下副檔名：

```text
*.txt
*.md
```

語意如下：

1. `.txt` 視為原始逐字稿。
2. `.md` 視為可讀文字來源。
3. `.md` 輸入不保留其原本 Markdown 結構，輸出時一律重新生成標準化 Markdown。

### 5.2 預設掃描規則

若未指定 `--file` 或 `--dir`，固定掃描：

```text
目前工作目錄第一層
```

第一版需排除：

1. 輸出子目錄 `formatted/`。
2. `_run-summary.txt`
3. `_environment.txt`
4. 明顯非輸入用途的隱藏暫存檔。

### 5.3 輸出目錄

預設輸出到：

```text
formatted/
```

具體規則：

1. 預設掃描目前目錄時，輸出到 `./formatted/`。
2. 使用 `--dir ./transcript` 時，輸出到 `./transcript/formatted/`。
3. 使用 `--file ./a/b/c.txt` 時，輸出到 `./a/b/formatted/`。
4. 若使用者明確指定 `--output-dir` 且為相對路徑，則一律相對於輸入 base directory 輸出。
5. 若使用者明確指定 `--output-dir` 且為絕對路徑，則輸出到該絕對路徑。
6. 工具不得接受會使輸出目錄等同輸入目錄本身的危險設定。

### 5.4 輸出檔名

若輸入：

```text
./episode-01.txt
```

輸出：

```text
./formatted/episode-01.md
```

若輸入：

```text
./episode-02.md
```

輸出：

```text
./formatted/episode-02.md
```

若同一批輸入中存在：

```text
lesson01.txt
lesson01.md
```

則兩者都會映射到：

```text
formatted/lesson01.md
```

此種情況必須在載入模型前直接報錯，不得默默跳過、覆蓋或依賴 `--force` 決定結果。

### 5.5 覆蓋策略

1. 若目標輸出檔已存在且未指定 `--force`，則跳過。
2. 若指定 `--force`，則允許覆蓋。
3. 批次模式下單檔失敗不得中止全部流程，應繼續處理其他檔案。
4. 若全部檔案在 preflight 階段即判定為 skipped，工具應直接輸出摘要並結束，不得載入模型。

---

## 6. 文字整理規則

### 6.1 三層規則模型

工具需明確區分以下三層規則：

1. 內建強制替換規則。
2. 外部強制替換詞彙表。
3. 外部 AI 參考指引。

這三層的語意不得混淆。

### 6.2 內建強制替換規則

內建規則用於修正常見且高確定性的音辨錯字，例如：

```text
POA => PUA
AIP => IP
物理資料 => 物料資料
攻深入局 => 躬身入局
```

此類規則屬於強制生效的替換規則，實作時應與外部詞彙表合併後再正式套用。

### 6.3 外部強制替換詞彙表

第一版格式固定為：

```text
來源 => 目標
```

例如：

```text
POA => PUA
偏西西 => 拼夕夕
預支差 => 預製菜
```

解析規則：

1. 忽略空白行。
2. 忽略以 `#` 開頭的註解行。
3. 每行必須可拆成 `來源 => 目標`。
4. 無法解析時，需回報行號與原始內容。
5. 正式替換前，應先完成文字正規化，例如簡體轉台灣繁體。
6. 替換規則應避免連鎖替換，不得因前一條替換結果再次命中下一條來源詞而改壞文字。

優先權規則：

1. 內建詞彙表與外部詞彙表應先合併，再正式套用。
2. 若來源詞相同，以外部詞彙表覆蓋內建詞彙表。
3. 合併完成後，應以單次非連鎖方式套用替換，不得先跑內建再跑外部。

### 6.4 外部 AI 參考指引

`--style-guide` 檔案內容不做結構解析，整份文字直接附加到 prompt。

其用途是提供：

1. 用語偏好。
2. 禁則。
3. 台灣慣用語替換方向。
4. 段落或標題風格偏好。

但其效果屬於模型參考，不得等同於強制替換規則。

---

## 7. Prompt 與模型規格

### 7.1 Prompt 結構

Prompt 至少應包含三部分：

1. 固定 system instruction。
2. 使用者輸入的逐字稿原文。
3. 額外 style guide 內容（若有）。

固定 system instruction 應要求模型：

1. 忠於原文，不新增原文沒有的內容。
2. 可修正根據上下文高度確定的語音辨識錯字、同音誤字與錯誤斷詞；若無法高度確定，必須保留原文，不得猜測。
3. 補上適當標點。
4. 根據語意分段。
5. 在主題自然切換時，適度加上簡潔的 Markdown 標題。
6. 標題需依據原文已存在的主題，不得憑空發明結論。
7. 轉為台灣繁體中文。
8. 若原文本來就包含英文術語、產品名、指令、路徑、型號或版本號，需保留其識別性，不得為了看起來自然就任意刪除。
9. 不得主動新增英文單字、分隔線、模型說明或其他與正文無關的內容。
10. 只輸出整理後的 Markdown 成品。

### 7.1.1 標題策略

標題規則至少需滿足以下條件：

1. 全文最多一個 H1。
2. 若檔名具有明確中文或中英混合主題，可作為 H1 候選提示。
3. 若檔名只有編號、日期或過度籠統，不得直接作為 H1。
4. 內容主題自然切換時可使用 H2。
5. 短篇且主題單一時，可以完全沒有段落標題。
6. 不得只因模型未產生任何標題，就無條件將任意檔名補成 H1。

### 7.2 預設模型

第一版預設模型：

```text
Qwen/Qwen2.5-3B-Instruct
```

選用理由：

1. 中文能力與指令遵循能力在本任務上屬於合理基準。
2. 對 `RTX 3050` 等較低顯示記憶體環境仍相對可行。
3. 作為第一版預設值，部署阻力較低。
4. 即使後續加入更高品質模型，仍保留作為標準模式與相容 fallback。

### 7.3 模型載入模式與 RTX 3080 10GB 建議

在 `RTX 3080 10GB` 上的建議策略：

1. 預設仍使用 `Qwen2.5-3B-Instruct`。
2. 若追求更高品質，可使用 `Qwen2.5-7B-Instruct` 搭配 `--quantization 4bit` 作為可選高品質模式。
3. `4bit` 模式屬於正式支援的載入選項，但不得取代 `3B` 一般模式。
4. 需保留 `3B` 作為低顯示記憶體環境，例如 `RTX 3050` 的可用路徑。
5. `4bit` 模式需明確回報依賴與載入錯誤，不得讓使用者只能看到難以理解的原始例外。

### 7.3.1 4bit 模式約束

若使用 `--quantization 4bit`，至少需符合以下規則：

1. 僅支援 CUDA 環境。
2. 需具備 `accelerate` 與 `bitsandbytes`。
3. 模型載入策略可使用 `device_map=auto`，但工具需自行處理輸入張量放置裝置。
4. 執行摘要與環境檔需明確記錄 `quantization`、實際 `device` 與 `dtype`。
5. 若依賴缺失、GPU 不支援或記憶體不足，需回報可操作的錯誤訊息。

### 7.4 其他模型相容性

若使用者指定其他模型，工具需：

1. 嘗試載入指定 tokenizer 與 model。
2. 若缺少 chat template 或對話格式不相容，需回報清楚錯誤。
3. 不應只丟出難以理解的原始 traceback 作為唯一訊息。

### 7.5 長度防護

第一輪修正必須加入輸入 token 長度檢查。

規則如下：

1. 工具需在正式生成前估算最終送入模型的完整 prompt token 數。
2. 計算範圍必須包含：
   - system prompt
   - 使用者逐字稿正文
   - style guide
   - 檔名提示
   - chat template
   - generation prompt
3. 若超過預設安全門檻，應明確報錯或拒絕處理。
4. 安全門檻應依據模型 context 上限、預留輸出 token 與安全餘裕決定。
5. 第一輪修正只要求做 length guard，不要求同步實作 chunking。

---

## 8. 執行流程

### 8.1 標準流程

工具應依序執行：

1. 解析 CLI 參數。
2. 驗證 `--file` / `--dir` 是否衝突。
3. 確定輸入來源與輸出目錄。
4. 掃描待處理檔案。
5. 驗證使用者明確指定的外部檔案：
   - 檢查 `--replace-dict` 路徑是否存在且格式正確。
   - 檢查 `--style-guide` 路徑是否存在且可讀取。
6. 做 preflight：
   - 檢查輸出檔名衝突。
   - 判斷哪些檔案會 skipped。
   - 若全部皆為 skipped，直接輸出摘要並結束。
7. 載入 tokenizer 與模型。
8. 逐檔讀取文字內容。
9. 先做文字正規化。
10. 合併內建與外部強制替換規則；來源詞相同時以外部規則優先。
11. 以單次非連鎖方式套用合併後的替換規則。
12. 組合 messages。
13. 套用 chat template，形成完整 prompt。
14. 檢查完整 prompt token 長度是否超過安全門檻。
15. 呼叫模型生成第一稿。
16. 對第一稿做保守清理。
17. 判斷是否需要 repair；第一稿清理後為空時必須進入 repair。
18. 若需 repair，生成 repair 稿。
19. 對 repair 稿做保守清理。
20. 若 repair 清理後仍為空，該檔記為 failed。
21. 驗證 repair 結果是否安全，並在第一稿與 repair 稿之間選擇較安全版本。
22. 寫入輸出檔案。
23. 輸出執行摘要。

### 8.2 輸出清理

模型輸出清理需處理：

1. Markdown code fence。
2. 明顯的多餘前言或後記。
3. 顯然不是成品內容的客套說明。

但清理規則不得過度寬鬆到誤刪合法 Markdown 內容。

補充規則：

1. 清理應優先處理明確的包裝格式，例如 code fence、固定前言與固定後記。
2. 不得僅因尾句含有「完成、修正、校正、排版、繁體」等一般詞彙而刪除。

### 8.3 Repair 流程

若第一稿品質異常，可進入第二次 repair 流程，但規則必須保守：

1. 不得僅因正文中包含正常英文術語就觸發 repair。
2. repair prompt 應允許保留原文本來就存在的英文術語、產品名、指令、路徑與版本號，並只移除無關英文說明。
3. 第一稿清理後若為空，應視為異常並強制進入一次 repair。
4. repair 結果不得為空。
5. 若 repair 清理後仍為空，該檔記為 failed。
6. repair 結果長度不得異常低於第一稿。
7. repair 結果不得無故遺失第一稿中的主要數字資訊。
8. repair 結果若明顯比第一稿更差，應保留第一稿。

第一輪修正至少需具備以下安全條件：

1. repair 清理後為空時，不得採用。
2. repair 清理後字元數若低於第一稿的預設安全比例，則不得採用；第一輪可採保守預設值，例如 70%。
3. 第一稿中的主要數字、日期或版本號若在 repair 中明顯遺失，不得採用。
4. 第一稿中的既有英文術語若在 repair 中大量消失，不得採用。
5. repair 若出現與正文無關的模型說明、客套話或包裝文字，不得採用。

特例規則：

1. 若第一稿清理後為空，repair 的安全檢查不得使用以第一稿為基準的長度比例、數字與英文術語保留規則。
2. 此時應改為直接與模型輸入正文比較，至少確認 repair 非空、未異常短於原始內容、主要數字資訊未遺失，且未出現模型說明或包裝文字。

---

## 9. 依賴與執行環境

### 9.1 核心依賴

第一版核心依賴：

```text
Python 3.10+
torch
transformers
opencc-python-reimplemented
```

### 9.2 建議環境

建議執行環境：

1. WSL2 或 Linux。
2. 支援 CUDA 的 NVIDIA GPU。
3. 至少可容納預設模型的本地磁碟空間與顯示記憶體。

### 9.3 首次執行行為

首次執行時，模型可能需從 Hugging Face 下載並快取到本機。

因此文件需明確說明：

1. 第一次執行可能需要網路。
2. 之後若模型已快取，可離線重複使用。
3. 預設公開模型情境下，不強制要求 `HF_TOKEN`。
4. 若指定 gated、private 或需授權的模型，需先滿足 Hugging Face 存取條件，例如 `HF_TOKEN` 或 CLI 登入。

### 9.4 可選量化依賴

若使用 `--quantization 4bit`，需額外具備：

```text
accelerate
bitsandbytes
```

若模型與環境支援，執行摘要或環境檔應盡量補充：

1. `accelerate_version`
2. `bitsandbytes_version`
3. `model_memory_bytes`

---

## 10. 執行摘要、進度與輸出檔

### 10.1 執行前摘要

正式處理前，工具應先輸出一段簡潔的執行摘要，至少包含：

1. 輸入來源。
2. 掃描深度。
3. 支援副檔名。
4. 待處理檔案數。
5. 輸出目錄。
6. 使用模型。
7. 量化模式。
8. 執行裝置與 dtype。
9. 是否載入外部替換表。
10. 是否載入 style guide。
11. 是否啟用 `--force`。

### 10.2 多檔進度輸出

多檔處理時，標準輸出應顯示簡化進度格式，讓使用者能快速掌握：

1. 總共有幾個作業。
2. 目前正在處理第幾個。
3. 每個檔案的結果是成功、跳過或失敗。

建議格式：

```text
[run] queued=12
[1/12] processing episode-01.txt
[1/12] done -> formatted/episode-01.md
[2/12] processing episode-02.txt
[2/12] skipped -> formatted/episode-02.md
[3/12] processing episode-03.md
[3/12] failed -> <reason>
```

第一版不要求：

1. 百分比進度條。
2. 預估剩餘時間。
3. Token 級別生成進度。

### 10.3 輸出摘要檔

工具在輸出目錄下應產生：

```text
_run-summary.txt
_environment.txt
```

用途如下：

1. `_run-summary.txt`：記錄本次執行設定、檔案總數、成功數、跳過數、失敗數。
2. `_environment.txt`：記錄 Python、`torch`、`transformers`、`accelerate`、`bitsandbytes`、CUDA、GPU、模型名稱、量化模式、模型 footprint、工作目錄與執行時間。

---

## 11. 錯誤處理與摘要

### 11.1 錯誤處理原則

工具需盡量回報可操作的錯誤訊息，而不是只有原始 traceback。

至少需涵蓋：

1. 缺少 `torch` 或 `transformers`。
2. 模型載入失敗。
3. 指定輸入檔不存在。
4. 指定副檔名不支援。
5. 替換詞彙表格式錯誤。
6. 指定目錄找不到可處理檔案。
7. 輸出路徑衝突。
8. 輸入 token 過長。
9. 空白輸出或明顯異常短輸出。

### 11.2 批次模式容錯

批次模式下：

1. 單一檔案失敗應記錄並繼續處理其他檔案。
2. 全部處理完後再輸出摘要。

### 11.3 結束摘要

結束時至少輸出：

1. 成功數。
2. 跳過數。
3. 失敗數。
4. 輸出目錄位置。

### 11.4 Exit Code

批次執行的 exit code 規則如下：

1. `0`：所有實際處理檔案均成功，或全部檔案均為 skipped。
2. `1`：參數錯誤、preflight 失敗、模型載入失敗，或批次中至少一個檔案處理失敗。

---

## 12. 檔案結構建議

目前建議採用 package 化結構：

```text
pyproject.toml
bin/transcript-polish
src/transcript_polish/
docs/SDD-transcript-polish.md
```

其中：

1. `src/transcript_polish/` 放主要 Python 程式碼。
2. `bin/transcript-polish` 只保留 repo 內開發入口用途。
3. 正式部署應優先使用 `pip install .` 產生的 CLI，而不是手動複製 `bin/transcript-polish`。
4. 若後續功能與依賴持續擴張，`transcript-polish` 應優先考慮拆成獨立 repo。
