# 安裝與部署

一般使用者不需要手動啟用 Python 虛擬環境。互動式安裝程式會建立專用 venv、同步套件，在 `~/bin/` 建立可直接執行的入口，並設定此使用者的預設模型模式。

預設位置：

```text
venv：   ~/.venvs/transcript-polish
指令：   ~/bin/transcript-polish
設定檔： ~/.config/transcript-polish/config.toml
```

## 1. 系統需求

Ubuntu / WSL：

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
```

需要 Python 3.10 以上。使用 NVIDIA GPU 時，系統也必須有可用的 NVIDIA Driver。

## 2. 取得專案

```bash
git clone <your-repo-url> ~/transcript-polish
cd ~/transcript-polish
```

已有 repo 時直接進入專案目錄即可。

## 3. 互動式安裝

```bash
bash scripts/install.sh
```

安裝程式會：

1. 檢查 Python 與 `venv`。
2. 建立或重用專用 venv。
3. 更新 venv 內的 `pip`、`setuptools`、`wheel`。
4. 讀取 `pyproject.toml`。
5. 檢查或詢問是否安裝 PyTorch。
6. 安裝核心 dependencies。
7. 詢問每個 `[project.optional-dependencies]` group。
8. 移除未選取但已安裝的 optional 直接套件。
9. 安裝本專案並建立 `~/bin/transcript-polish`。
10. 驗證 CLI、PyTorch、量化套件與 dependency 狀態。
11. 詢問是否將 Quality 設為此使用者的預設模式。

### 已有 venv

若環境已存在，會詢問：

```text
[r] 保留環境並同步套件
[c] 刪除後重新建立
[q] 取消
```

保留環境時，只同步需要變動的套件。

### 套件版本

- 已安裝版本符合 requirement 時，pip 不會重裝。
- 版本不符合時才安裝或更新。
- optional group 選擇否時，該 group 直接列出的已安裝套件會被移除。
- 共用或傳遞相依套件可能保留。
- 最後會執行 `pip check`。

### 專案版本

安裝程式讀取 `pyproject.toml` 的 `project.version`。若相同版本已安裝且 CLI 入口存在，主程式不會重裝。因此正式發布程式修改時應提高版本號。

### PyTorch

`torch` 沒有直接放入核心 dependencies，因為 CPU 與 CUDA 環境可能需要不同版本。

- 已安裝：顯示版本與 CUDA 狀態，不重裝。
- 未安裝：詢問是否執行一般的 `pip install torch`。
- 需要特定 CUDA wheel 時可選否，依 PyTorch 官方方式安裝後再重跑。

### Optional groups

目前包括：

```text
quantization：accelerate、bitsandbytes，供 Quality 模式使用
dev：pytest，供開發與測試使用
```

沒有可用 CUDA 時，`quantization` 預設選擇否。

### 預設模型模式

模式對應如下：

```text
standard：Qwen/Qwen2.5-3B-Instruct、無量化
quality： Qwen/Qwen2.5-7B-Instruct、4-bit
```

若已安裝完整 `quantization` group，安裝程式會詢問：

```text
是否將 Quality 模式（7B、4-bit）設為此使用者的預設模式？
```

設定會寫入：

```text
~/.config/transcript-polish/config.toml
```

例如：

```toml
mode = "quality"
```

若本次未安裝完整量化套件，預設模式會維持或改回 `standard`，避免留下無法執行的 Quality 預設。

## 4. 安裝後使用

使用設定檔中的預設模式：

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

若安裝程式剛把 `~/bin` 加入 `~/.bashrc`：

```bash
source ~/.bashrc
```

一般使用不需要執行：

```bash
source ~/.venvs/transcript-polish/bin/activate
```

### 進階模型參數

仍可直接指定：

```bash
transcript-polish \
  --model Qwen/Qwen2.5-7B-Instruct \
  --quantization 4bit \
  --dir ./transcript
```

明確指定的 `--model` 或 `--quantization` 會覆蓋 mode 對應值。執行時 `[config]` 會顯示最後實際採用的值。

優先順序：

1. `--model` / `--quantization`
2. `--mode`
3. 使用者設定檔
4. 內建 `standard`

## 5. 自訂位置

```bash
TRANSCRIPT_POLISH_VENV="$HOME/apps/transcript-polish-venv" \
  bash scripts/install.sh
```

```bash
TRANSCRIPT_POLISH_BIN_DIR="$HOME/.local/bin" \
  bash scripts/install.sh
```

```bash
PYTHON_BIN=python3.12 bash scripts/install.sh
```

使用者設定檔遵循 `XDG_CONFIG_HOME`；未設定時使用 `~/.config`。

## 6. 更新

```bash
cd ~/transcript-polish
git pull
bash scripts/install.sh
```

相同專案版本不重裝；dependencies 只處理不符合 requirement 的部分。

## 7. 開發者安裝

```bash
source "$HOME/.venvs/transcript-polish/bin/activate"
python -m pip install -e '.[dev,quantization]'
pytest
deactivate
```

Editable install 會直接使用 repo 原始碼。

## 8. 解除安裝

```bash
bash scripts/uninstall.sh
```

會詢問後移除使用者入口與專用 venv。Hugging Face 模型快取不會自動刪除。使用者設定檔目前會保留，方便日後重新安裝沿用；不需要時可自行刪除：

```bash
rm -rf ~/.config/transcript-polish
```

## 9. 常見問題

指令找不到：

```bash
ls -l ~/bin/transcript-polish
source ~/.bashrc
```

檢查目前解析出的模式：

```bash
transcript-polish --help
```

實際執行時會顯示：

```text
[config] mode=quality
[config] mode_source=user_config
[config] model=Qwen/Qwen2.5-7B-Instruct
[config] quantization=4bit
```

檢查 PyTorch / CUDA：

```bash
"$HOME/.venvs/transcript-polish/bin/python" -c \
  "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

若使用者設定檔損壞，CLI 會清楚報錯，不會默默忽略。
