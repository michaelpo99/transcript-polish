# SDD: transcript-polish

最後更新：2026-06-14

## 1. 產品目標

`transcript-polish` 是一支 **conservative transcript polishing** CLI。

它的固定定位是：

> 將 ASR 原始逐字稿整理成可讀、忠實、保留講者原本語氣與詞彙選擇的繁體中文 Markdown。

這支工具：

1. 不執行 WhisperX。
2. 不產生會議紀錄。
3. 不做摘要或文章化改寫。
4. 只處理已存在的 `.txt` / `.md` 逐字稿。

## 2. 產品邊界

### 2.1 可以做

1. 簡體轉繁體。
2. 補標點、斷句與分段。
3. 修正高度確定的 ASR 錯字。
4. 適度加入方便閱讀的標題。
5. 保留口語、中英夾雜、講者標記、數字與原始資訊順序。

### 2.2 不應做

1. 摘要或濃縮。
2. 改寫成正式文章。
3. 把正確英文口語翻成中文。
4. 為了通順新增原文沒有的資訊。
5. 產生會議紀錄、決議或待辦事項。
6. 自動把 `SPEAKER_00` 替換成人名。

## 3. CLI 目標

### 3.1 基本用法

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

### 3.2 參數

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
    載入外部替換詞彙表。

--style-guide <path>
    載入單次任務的附加偏好。

--prompt-config <path>
    載入正式 prompt 設定檔。

--output-dir <name-or-path>
    指定輸出子目錄名稱或路徑。
    若未指定，預設為 formatted。

-f, --force
    覆蓋已存在的輸出檔。
```

### 3.3 使用者優先順序

```text
使用者明確指定 > 預設 conservative 設定 > 內建安全預設值
```

## 4. 輸入與輸出

### 4.1 輸入

1. 預設掃描目前目錄第一層。
2. 支援 `.txt`、`.md`。
3. 不遞迴子目錄。
4. 跳過 `formatted/`、`_run-summary.txt`、`_environment.txt`。

### 4.2 輸出

1. 預設輸出到來源目錄下的 `formatted/`。
2. 檔名固定輸出為 `<stem>.md`。
3. 同 stem 的 `.txt` / `.md` 衝突必須在載入模型前報錯。
4. 全 skipped 時不得載入模型。

## 5. Prompt 與語言策略

### 5.1 核心語言原則

Prompt 必須明確要求：

1. 忠於原文，不新增原文沒有的資訊。
2. 保留講者的口語、語助詞與中英夾雜。
3. 不得翻譯正確英文口語。
4. 修正 ASR 錯字的目的是還原原話，不是改善遣詞用字。
5. 繁體化只處理字形，不主動做詞彙翻譯或文體提升。

### 5.2 Prompt 外部化

目前應支援：

```bash
--prompt-config <path>
```

設定檔至少包含：

```text
system_prompt
repair_prompt
final_user_instruction
repair_user_instruction
```

第一版實作可先採 JSON 格式。

第一版只要求一套正式 conservative prompt，不要求 article / meeting 等多種 profile。

### 5.3 style-guide 與 prompt-config 邊界

1. `prompt-config` 是產品級規則。
2. `style-guide` 是單次任務附加偏好。
3. `style-guide` 不得覆蓋核心 conservative 定位。

## 6. 替換規則

### 6.1 下一版原則

程式內不應保留語料專屬的硬編碼 replacements。

例如以下規則不應作為全域預設：

```text
POA -> PUA
AIP -> IP
物理資料 -> 物料資料
```

### 6.2 replace-dict

這類規則應移到外部 `--replace-dict`。

第一版格式可維持：

```text
來源 => 目標
```

解析規則：

1. 忽略空白行。
2. 忽略 `#` 註解行。
3. 需回報格式錯誤行號。
4. 仍採單次、非連鎖替換。

## 7. 講者標記保留

對以下格式：

```text
[00:01:12] SPEAKER_00: 我覺得這個很 low
[00:01:18] SPEAKER_01: 對啊，這個真的很貴
```

下一版至少必須保證：

1. 原樣保留時間戳。
2. 原樣保留 `SPEAKER_XX`。
3. 不重新編號。
4. 不合併不同講者。
5. 不把發言移到其他講者。
6. 只修正標記後的正文。

第一版先以 prompt 與測試保護，不要求立即開發 parser。

## 8. 模型策略

| 模式 | 模型 | 定位 |
| --- | --- | --- |
| Standard / Fast | `Qwen/Qwen2.5-3B-Instruct` | 低門檻、速度優先 |
| Quality | `Qwen/Qwen2.5-7B-Instruct` + `--quantization 4bit` | 正式輸出、較佳語意與分段 |

量化模式應維持：

1. `BitsAndBytesConfig` 4-bit。
2. `device_map=auto`。
3. CPU / disk offload 防護。
4. 清楚回報 `accelerate` / `bitsandbytes` 缺失。

## 9. P0 實作範圍

### 9.1 本輪建議完成

1. 移除程式碼內的特定 replacements。
2. 將 prompt 外部化。
3. 更明確保留原始風格。
4. 支援講者分離格式保護。
5. 修復 `docs/INSTALL.md`。
6. 修正兩個小問題：
   - `[run] queued` 應顯示真正的 `queued_jobs`
   - `generate_response()` 應使用 `MAX_NEW_TOKENS`

### 9.2 暫不放進下一版

1. 會議紀錄產生。
2. 摘要、決議、待辦事項。
3. 多種文章化 profile。
4. 固定執行第二次 repair。
5. 完整 chunking。
6. 更多量化後端，例如 AWQ、GPTQ、GGUF、Ollama。

## 10. P1 測試

下一版應優先建立：

```text
tests/test_replacements.py
tests/test_output_paths.py
tests/test_response_cleaning.py
tests/test_repair_validation.py
tests/test_cli_preflight.py
tests/test_prompt_behavior.py
```

必要案例包括：

1. `很 low` 不得改成 `很低`。
2. `feedback` 不得翻成中文。
3. 不得新增原文沒有的角色或資訊。
4. 講者標記、時間戳及講者順序必須保留。
5. 全 skipped 不載模型。
6. 同 stem `.txt` / `.md` 提前報衝突。
7. 空輸出算失敗。
8. repair 遺失數字或術語時不採用。

## 11. 驗收重點

評估模型與 prompt 時，不得只看「文字更自然」。

至少要分別觀察：

1. 正確修正數。
2. 漏修數。
3. 誤改數。
4. 新增資訊數。
5. 口語與中英夾雜保留程度。
6. 分段與標點品質。

正式輸出以：

```text
忠實度 > 語意保留 > 可讀性 > 文體漂亮
```

為優先順序。
