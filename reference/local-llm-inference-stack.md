# 本地 LLM 推論技術棧入門

這篇文章說明 `transcript-polish` 背後使用的 Python 與本地 AI 技術。目標不是介紹神經網路數學，而是讓熟悉一般軟體開發、Java、套件管理與執行環境的人，可以理解這個工具由哪些元件組成、各自負責什麼，以及常見問題應從哪一層排查。

---

## 1. 先看整體架構

`transcript-polish` 的主要處理流程可以簡化成：

```text
transcript-polish 指令
        ↓
Python CLI 程式
        ↓
讀取逐字稿、OpenCC 正規化、套用 replacements
        ↓
Transformers 載入 tokenizer 與 Qwen 模型
        ↓
PyTorch 執行模型運算
        ↓
CUDA 將運算交給 NVIDIA GPU
        ↓
模型產生整理後文字
        ↓
Python 程式清理、驗證並寫入 Markdown
```

其中：

- Python 負責整體流程與檔案處理。
- Transformers 負責理解如何載入及使用不同 LLM。
- PyTorch 負責真正的神經網路數學運算。
- CUDA 讓 PyTorch 可以使用 NVIDIA GPU。
- Qwen 是實際執行文字整理工作的語言模型。
- OpenCC 與 replacements 則負責可預期、確定性的文字轉換。

---

## 2. 用 Java 世界來類比

以下類比不是完全等價，但有助理解各元件的角色。

| Python / AI 世界 | Java 世界的近似概念 |
| --- | --- |
| Python | Java 語言與執行環境 |
| `pip` | Maven / Gradle 的套件安裝功能 |
| `pyproject.toml` | `pom.xml` 或 `build.gradle` |
| Python package | Java package 加 JAR library |
| PyPI | Maven Central |
| `venv` | 每個專案獨立的一套 JDK 周邊與 dependency 目錄 |
| Hugging Face Hub | 大型模型用的 artifact repository |
| Transformers | 通用模型 framework、loader 與 driver |
| PyTorch | 神經網路 runtime 與數值運算引擎 |
| CUDA | NVIDIA GPU 的通用運算平台 |
| Qwen 模型 | 具體下載並執行的模型 artifact |

需要注意的是，LLM 模型通常有數 GB，遠大於一般 Java dependency。

---

## 3. Python 在這個專案中的角色

Python 是 `transcript-polish` 的主要程式語言，負責：

- 解析 CLI 參數。
- 掃描輸入檔案。
- 讀寫 `.txt` 與 `.md`。
- 載入設定檔與 replacement dictionary。
- 建立 prompt。
- 呼叫模型。
- 檢查模型輸出是否為空、過短或遺失重要資訊。
- 寫出整理後的 Markdown 與執行摘要。

專案中的 `pyproject.toml` 大致相當於 Maven 專案的 `pom.xml`，會定義：

- package 名稱與版本。
- 支援的 Python 版本。
- 必要 dependency。
- optional dependency。
- 安裝後產生的 CLI 指令。

### 3.1 `pip`

`pip` 是 Python 的套件安裝工具，例如：

```bash
pip install transformers
pip install .
pip install '.[quantization]'
```

`pip install .` 表示安裝目前目錄中的 Python 專案。

### 3.2 `venv`

`venv` 是 Python 的虛擬環境。它讓每個專案有自己的一套 Python dependency，不會和其他專案互相污染。

```bash
python3 -m venv ~/.venvs/transcript-polish
source ~/.venvs/transcript-polish/bin/activate
```

可以把它理解為：

> 為某個專案建立獨立的 Python runtime 與 library classpath。

這在 AI 專案特別重要，因為 PyTorch、Transformers、bitsandbytes 與 CUDA 之間存在版本相容性問題。

---

## 4. PyTorch / `torch` 是什麼

套件名稱是 `torch`，產品名稱是 **PyTorch**。

PyTorch 是神經網路的數學執行引擎，主要負責：

- 建立與操作 tensor。
- 執行矩陣乘法。
- 載入模型參數。
- 將模型與資料放到 CPU 或 GPU。
- 呼叫 CUDA。
- 執行模型推論。

### 4.1 Tensor 是什麼

Tensor 可以理解為多維陣列：

```text
純量      0 維
向量      1 維
矩陣      2 維
更高維資料 3 維以上
```

LLM 的文字最後都會轉成數字，並以大量 tensor 進行運算。

PyTorch 並不知道「逐字稿」、「繁體中文」或「PUA」的語意。它只知道如何根據模型結構，對大量數字執行計算。

### 4.2 為何 PyTorch 通常不直接寫入一般 dependency

PyTorch 有不同安裝版本，例如：

- CPU 版。
- 不同 CUDA runtime 的 GPU 版。
- 不同作業系統與硬體版本。

因此專案通常要求使用者先依自己的環境安裝合適的 PyTorch，再安裝應用程式。這類似需要先準備正確 JDK、Oracle Client 或 native library。

---

## 5. Transformer 與 Transformers 的差別

這兩個名詞容易混淆。

### Transformer

Transformer 是一種神經網路架構。現代多數 LLM，例如 Qwen、Llama、GPT，都是以 Transformer 為基礎。

### Transformers

Transformers 是 Hugging Face 提供的 Python 函式庫名稱。

它負責：

- 從 Hugging Face Hub 下載模型。
- 讀取模型設定。
- 建立正確的模型結構。
- 載入模型權重。
- 載入 tokenizer。
- 套用模型的聊天格式。
- 呼叫 `model.generate()` 產生文字。

常見程式如下：

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)
```

這段程式的意思是：

> 根據模型名稱，自動取得適合的 tokenizer、模型設定和模型權重。

可以將 Transformers 理解為各種 LLM 的通用 loader、driver 與 framework。

---

## 6. Hugging Face 是什麼

Hugging Face 同時提供多種服務與工具：

- Hugging Face Hub：模型與資料集倉庫。
- Transformers：模型載入與推論函式庫。
- Accelerate：裝置配置與模型載入工具。
- Tokenizer 工具。
- 模型下載、授權與快取機制。

模型名稱：

```text
Qwen/Qwen2.5-7B-Instruct
```

可以理解為：

```text
發布者 / artifact 名稱
```

第一次執行 `from_pretrained()` 時，模型通常會下載到本機 Hugging Face cache。後續執行會直接使用本機快取。

這和 Maven 第一次下載 dependency 到本機 repository 類似，但模型檔案可能有數 GB。

### 6.1 Python 套件和模型是分開的

執行：

```bash
pip install transformers
```

只會安裝 Transformers 函式庫，不會同時安裝 Qwen 模型。

模型是在第一次執行 `from_pretrained()` 時才下載。

刪除 Python `venv` 也不一定會刪除 Hugging Face 模型快取。

---

## 7. Qwen 模型到底是什麼

Qwen 模型大致包含：

1. 模型結構設定。
2. Tokenizer。
3. 聊天格式設定。
4. 大量模型參數，也稱為 weights。

模型參數是訓練後得到的數字。模型的語言能力主要儲存在這些數十億個數值中。

### 7.1 3B 與 7B

- 3B：約 30 億個參數。
- 7B：約 70 億個參數。

模型越大，通常越有能力理解上下文與複雜語意，但需要更多：

- 磁碟空間。
- 系統 RAM。
- GPU VRAM。
- 推論時間。

### 7.2 Instruct 是什麼

`Qwen2.5-7B-Instruct` 中的 `Instruct` 表示模型已經針對「遵從人類指令」做過調整。

它比較適合接受：

```text
請依照以下規則整理逐字稿……
```

Base model 則比較適合續寫、研究或再訓練，不一定適合直接當 CLI 的文字整理模型。

---

## 8. Tokenizer 是什麼

LLM 不直接讀取字串。

例如：

```text
我覺得這個很 low
```

會經過：

```text
文字
→ tokenizer 切成 token
→ token ID
→ 模型運算
→ 新 token ID
→ tokenizer 解碼
→ 輸出文字
```

Token 不一定等於一個中文字或一個英文單字。有時是一個字，有時是半個英文單字，有時是一段常見字串。

因此模型限制通常不是用字數，而是用 token 數。

---

## 9. CUDA 是什麼

CUDA 是 NVIDIA 提供的 GPU 通用運算平台。它讓一般程式不只用 GPU 畫圖，也能用 GPU 執行矩陣與神經網路運算。

整體關係是：

```text
Python 程式
   ↓
PyTorch
   ↓
CUDA runtime
   ↓
NVIDIA Driver
   ↓
RTX 3080
```

### 9.1 NVIDIA Driver

Driver 讓作業系統能控制顯示卡。沒有正確 Driver，PyTorch 無法使用 GPU。

### 9.2 CUDA runtime

CUDA runtime 提供執行 GPU 計算所需的函式庫。

許多 PyTorch GPU 安裝包已附帶所需的 CUDA runtime，因此只是執行現成模型時，不一定要另外安裝完整 CUDA Toolkit。

### 9.3 CUDA Toolkit

完整 CUDA Toolkit 還包含：

- CUDA 編譯器。
- Header。
- 開發工具。
- 額外原生函式庫。

通常在編譯自訂 CUDA 程式或某些 native extension 時才更需要。

---

## 10. 為何使用 GPU

LLM 推論需要大量矩陣乘法。

CPU 與 GPU 的粗略差異：

```text
CPU
- 核心數較少
- 單核心能力強
- 適合一般程式邏輯

GPU
- 有大量平行計算單元
- 適合大量相似的矩陣計算
- 適合神經網路推論
```

CPU 也可以執行模型，但通常會慢很多。

---

## 11. VRAM 和一般 RAM 的差別

電腦可能有：

```text
系統 RAM：32GB 或 64GB
GPU VRAM：10GB
```

模型要有效率地在 GPU 推論，主要權重與推論資料必須放進 VRAM。

即使系統 RAM 很大，模型放不進 VRAM，仍可能發生：

- CUDA out of memory。
- 模型部分放到 CPU。
- 推論速度大幅下降。
- 模型無法載入。

`transcript-polish` 的 4-bit 模式會檢查模型是否被分配到 CPU 或磁碟，避免在使用者不知情的情況下極慢執行。

---

## 12. FP16、4-bit 與量化

模型參數需要以某種數值格式儲存。

### 12.1 FP16

FP16 表示每個參數大致使用 16 bits，也就是 2 bytes。

粗略估算：

```text
3B × 2 bytes ≈ 6GB
7B × 2 bytes ≈ 14GB
```

這只是模型權重，尚未包含推論暫存與其他開銷。

所以 7B FP16 通常無法完整放進 RTX 3080 10GB。

### 12.2 4-bit 量化

4-bit 量化將模型權重壓縮到每個參數大約 4 bits：

```text
7B × 0.5 bytes ≈ 3.5GB
```

實際使用仍會高於 3.5GB，因為還有：

- 量化 metadata。
- 部分未量化層。
- 推論暫存。
- KV cache。
- CUDA runtime。

量化會犧牲部分數值精度，但能讓更大的模型放入有限 VRAM。

因此：

```text
3B FP16
與
7B 4-bit
```

雖然 7B 經過量化，但因模型規模更大，整體品質仍可能優於 3B FP16。是否真的更好，仍要用相同測試資料比較。

---

## 13. bitsandbytes 是什麼

`bitsandbytes` 是低位元量化相關的套件。

在本專案中，它主要負責：

- 以 4-bit 儲存模型權重。
- 使用 NF4 量化格式。
- 執行時以 FP16 做部分計算。
- 降低 VRAM 使用量。

可以把它理解為：

> 讓 PyTorch 能有效率使用壓縮後模型權重的量化擴充元件。

它不會直接讓文字變得更好；品質提升主要來自可以使用更大的模型。

---

## 14. Accelerate 是什麼

`accelerate` 是 Hugging Face 的模型部署與裝置配置工具。

它可以協助：

- 決定模型應放在哪個裝置。
- 使用 `device_map="auto"` 配置模型。
- 降低模型載入時的記憶體峰值。
- 協調 GPU / CPU 的模型分配。

在 `transcript-polish` 中，它主要協助 4-bit 模型正確載入 GPU。

它不負責修正文句，也不會提高模型本身的語言能力。

---

## 15. OpenCC 是什麼

OpenCC 是簡繁中文轉換工具，不是 AI。

它的特性是：

- 快速。
- 結果相對固定。
- 不需要 GPU。
- 適合做確定性的文字正規化。

目前專案使用的設定可能不只轉換字形，也可能轉換地區詞彙。

因此要區分：

```text
簡體字 → 繁體字
通常是預期的字形轉換

大陸詞彙 → 台灣詞彙
可能已涉及詞彙或風格改寫
```

若工具定位是保守保留逐字稿原貌，就需要特別確認 OpenCC 設定是否符合產品政策。

---

## 16. Replacement dictionary 與 Prompt 的差別

本工具同時使用確定性規則與 LLM 判斷。

### 16.1 Replacement dictionary

例如：

```text
驢臣部隊馬嘴 => 驢唇不對馬嘴
```

程式直接替換，結果確定且容易測試。

優點：

- 穩定。
- 可重現。
- 不需要模型判斷。

缺點：

- 只適用於已知錯誤。
- 規則可能在其他上下文誤傷。
- 不適合將個人語料規則寫死在通用程式中。

### 16.2 Prompt

例如：

```text
只修正依上下文高度確定的語音辨識錯字。
```

這是要求 LLM 根據語意判斷。

優點：

- 可處理未預先列出的錯誤。
- 能考慮上下文。

缺點：

- 結果不完全可預測。
- 可能漏修。
- 也可能誤改或補充原文沒有的資訊。

因此 `transcript-polish` 的合理分工是：

```text
OpenCC
    確定性中文正規化

replacement dictionary
    確定性特定詞彙修正

LLM prompt
    語意判斷、標點、分段與高信心錯字修正
```

---

## 17. Prompt、System Prompt 與 Style Guide

### System Prompt

System prompt 定義工具的核心行為，例如：

- 是否允許改寫。
- 是否必須保留講者語氣。
- 是否保留中英夾雜。
- 哪些錯誤可以修正。
- 哪些內容不可新增。

### Style Guide

Style guide 是某一批稿件的補充規則，例如：

- 公司名稱寫法。
- 人名對應。
- 特定領域用詞。
- 標題偏好。

### Replacement dictionary

Replacement dictionary 是強制、確定性的字串替換。

三者不應混為一談：

```text
System Prompt
    產品核心政策

Style Guide
    某批內容的編輯偏好

Replacement Dictionary
    已確認錯詞的強制替換
```

---

## 18. 推論和訓練的差別

### 推論 Inference

載入已訓練模型，提供 prompt，取得輸出。

```text
載入 Qwen
→ 提供逐字稿與規則
→ 取得整理結果
```

`transcript-polish` 只做推論。

### 訓練或 Fine-tuning

會修改模型權重，需要：

- 訓練資料。
- 更複雜的 GPU 環境。
- 較長處理時間。
- 專門的訓練與驗證流程。

目前 replacements、style guide 與 prompt 都不會讓 Qwen 永久學會你的偏好。每次執行時，這些規則都會重新送進模型。

---

## 19. Context Window 是什麼

模型一次能處理的 token 總量有限，稱為 context window。

這個總量通常包含：

- System prompt。
- 原始逐字稿。
- Style guide。
- 檔名提示。
- Chat template。
- Repair 階段的第一稿。
- 模型要生成的輸出。

因此不能只看逐字稿字數。

即使模型規格宣稱支援很長的 context，實際能否使用還會受 VRAM 限制。

---

## 20. KV Cache 是什麼

模型生成文字時，需要記住前面 token 的中間計算結果，這些資料通常稱為 KV cache。

輸入越長、輸出越長，KV cache 通常越大，VRAM 使用量也越高。

因此：

> 模型權重能放入顯卡，不代表任意長的逐字稿都能處理。

---

## 21. `max_new_tokens` 是什麼

`max_new_tokens` 表示模型最多能生成多少個新 token。

例如：

```text
max_new_tokens = 4096
```

不代表 4096 個中文字，而是最多產生 4096 個 tokenizer token。

如果逐字稿很長，模型輸出可能碰到上限而被截斷。因此程式需要：

- 在生成前計算 prompt token。
- 預留輸出空間。
- 驗證輸出是否異常短或中途截斷。

---

## 22. Temperature、Sampling 與可重現性

LLM 可以使用較隨機或較確定的生成方式。

`transcript-polish` 使用：

```text
do_sample=False
```

這代表傾向採較確定性的生成方式，適合逐字稿整理，因為這不是創意寫作任務。

但即使如此，不同：

- 模型版本。
- PyTorch 版本。
- Transformers 版本。
- GPU 環境。
- Prompt。

仍可能讓輸出有所差異。

---

## 23. ASR 與 Diarization

### ASR

ASR 是 Automatic Speech Recognition，自動語音辨識，也就是語音轉文字。

WhisperX 產生的錯字，例如：

```text
驢唇不對馬嘴
→ 驢臣部隊馬嘴
```

稱為 ASR 誤辨識。

### Diarization

Diarization 是講者分離，判斷哪一段由哪一位講者說。

例如：

```text
SPEAKER_00: 我認為這個方案可以。
SPEAKER_01: 但成本可能太高。
```

`SPEAKER_00` 不代表系統知道真實姓名，只表示系統認為這些片段屬於同一位講者。

`transcript-polish` 應保留：

- 講者標記。
- 講者順序。
- 發言歸屬。
- 時間戳。

不應自行猜測真實姓名或重新分配內容。

---

## 24. 一次完整執行實際發生什麼

以下指令：

```bash
transcript-polish \
  --model Qwen/Qwen2.5-7B-Instruct \
  --quantization 4bit \
  --file transcript.txt
```

內部大致會依序執行：

1. Python 解析 CLI 參數。
2. 檢查輸入與輸出路徑。
3. 讀取逐字稿。
4. OpenCC 做中文正規化。
5. 套用 replacement dictionary。
6. Transformers 載入 tokenizer。
7. Transformers 建立 Qwen 模型。
8. bitsandbytes 以 4-bit 載入權重。
9. Accelerate 將模型配置到 GPU。
10. 程式組合 system prompt、逐字稿與 style guide。
11. Tokenizer 將文字轉成 token ID。
12. PyTorch 透過 CUDA 在 GPU 執行模型。
13. 模型產生新的 token ID。
14. Tokenizer 將 token ID 解碼成文字。
15. Python 清理模型輸出。
16. 驗證輸出是否為空、過短、遺失數字或重要英文詞。
17. 寫出 Markdown、`_run-summary.txt` 與 `_environment.txt`。

真正執行 LLM 推論的核心通常只是：

```python
model.generate(...)
```

但前後的大量程式碼，是為了安全準備輸入、管理硬體與驗證輸出。

---

## 25. 為何版本組合很重要

本地 AI 工具同時涉及：

- Python 版本。
- PyTorch 版本。
- Transformers 版本。
- Accelerate 版本。
- bitsandbytes 版本。
- NVIDIA Driver。
- CUDA runtime。
- 模型版本。
- Prompt 版本。

它們之間可能存在相容性限制。

這類問題有點像：

```text
JDK 版本
+ Framework 版本
+ JDBC Driver
+ Native Client
+ 作業系統
```

但 Python AI 生態的版本變動通常更快。

因此專案應保留一套實際驗證成功的版本組合，並在 `_environment.txt` 中記錄環境資訊。

---

## 26. 常見問題應從哪一層排查

### 指令找不到

優先檢查：

- venv 是否啟用。
- package 是否已 `pip install .`。
- console script 是否在 PATH。

### Python import 失敗

優先檢查：

- 是否進入正確 venv。
- dependency 是否安裝。
- Python 版本是否相容。

### 模型下載失敗

優先檢查：

- 網路。
- Hugging Face 權限。
- `HF_TOKEN`。
- 模型名稱。
- 磁碟空間。

### CUDA 不可用

優先檢查：

- NVIDIA Driver。
- WSL GPU 支援。
- `torch.cuda.is_available()`。
- 是否安裝了 GPU 版 PyTorch。

### CUDA out of memory

優先檢查：

- 模型是否太大。
- 是否使用 4-bit。
- 是否有其他程式占用 VRAM。
- 輸入 context 是否太長。
- `max_new_tokens` 是否過大。

### 輸出品質不好

優先區分：

- 原始 ASR 是否錯得太嚴重。
- Prompt 是否過於保守或過度改寫。
- 3B 模型能力是否不足。
- 是否需要 7B 4-bit。
- 是否有確定錯詞應放入 replacement dictionary。
- 是否是 OpenCC 詞彙轉換造成風格改變。

### 輸出變自然但不忠實

這通常不是底層 CUDA 或 PyTorch 問題，而是：

- Prompt 政策。
- 模型傾向。
- Style guide。
- Repair 流程。

例如把「很 low」改成「很低」，屬於不必要翻譯或改寫，不是 ASR 修正。

---

## 27. 維護這個工具需要掌握到什麼程度

現階段不需要先學會神經網路數學，也不必理解 Transformer 每一層的公式。

建議先掌握：

1. Python package、`pip` 與 `venv`。
2. PyTorch 是模型數學執行引擎。
3. Transformers 負責載入與操作模型。
4. CUDA 讓 PyTorch 使用 NVIDIA GPU。
5. 模型權重是另外下載的大型 artifact。
6. 量化用較低數值精度換取較少 VRAM。
7. Token、context window 與 `max_new_tokens` 會限制長文處理。
8. Prompt 是不確定性的語意規則。
9. OpenCC 與 replacements 是較確定性的程式規則。
10. 本工具只做 inference，不做訓練。
11. Diarization 標記代表講者群組，不代表真實姓名。
12. 版本與執行環境必須被記錄，才能重現問題。

---

## 28. 元件速查表

| 元件 | 主要責任 | 是否直接影響文字品質 |
| --- | --- | --- |
| Python | CLI、流程、檔案與驗證 | 間接 |
| `venv` | 隔離 dependency | 否 |
| `pip` | 安裝 Python package | 否 |
| `pyproject.toml` | 專案與 dependency 定義 | 間接 |
| PyTorch / `torch` | 模型數學執行 | 間接 |
| Transformers | 載入 tokenizer 與模型、生成文字 | 間接 |
| Hugging Face Hub | 儲存與下載模型 | 否 |
| Qwen | 實際理解並整理文字 | 是 |
| CUDA | 使用 NVIDIA GPU | 否，主要影響速度與可載入規模 |
| NVIDIA Driver | 控制 GPU | 否 |
| bitsandbytes | 4-bit 量化載入 | 間接，讓較大模型可用 |
| Accelerate | 裝置配置與模型載入 | 否 |
| OpenCC | 簡繁與詞彙正規化 | 是，且為確定性轉換 |
| Replacement dictionary | 強制修正已知詞彙 | 是，且為確定性轉換 |
| System prompt | 定義模型行為政策 | 是 |
| Style guide | 定義某批稿件的偏好 | 是 |
| Tokenizer | 文字與 token ID 互轉 | 間接 |
| Context window | 限制一次可處理的總 token | 間接 |
| KV cache | 保存生成過程的中間狀態 | 否，主要影響 VRAM |

---

## 29. 最後的整體理解

可以把 `transcript-polish` 看成三層：

```text
第一層：一般應用程式
Python CLI、檔案處理、設定、驗證、輸出

第二層：AI Framework
Transformers、PyTorch、Accelerate、bitsandbytes

第三層：硬體與模型
Qwen 模型、CUDA、NVIDIA Driver、RTX GPU
```

而文字處理策略也分成三層：

```text
確定性字形轉換
OpenCC

確定性已知錯詞修正
Replacement dictionary

需要上下文判斷的整理
LLM + Prompt
```

理解這兩組分層後，大多數設計與問題都能先定位到正確層次，再決定要修改程式、設定、Prompt、模型，還是執行環境。