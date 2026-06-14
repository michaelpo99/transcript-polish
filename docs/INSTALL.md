# 安裝程序

本文件只說明 `transcript-polish`。

它不依賴 WhisperX 環境，但需要自己的 Python 環境，以及你自行準備好的 `torch`。

## 1. 安裝系統依賴

在 Ubuntu / WSL：

```bash
sudo apt update
sudo apt install -y python3-venv
```

若要使用 GPU，請先依你的 CUDA 環境準備對應版本的 `torch`。

## 2. 取得專案

```bash
cd ~/transcript-polish
```

或：

```bash
git clone <your-repo-url>
cd transcript-polish
```

## 3. 建立虛擬環境

```bash
python3 -m venv "$HOME/.venvs/transcript-polish"
source "$HOME/.venvs/transcript-polish/bin/activate"
python -m pip install --upgrade pip setuptools wheel
```

## 4. 安裝 package

先安裝合適版本的 `torch`，再安裝本專案。

`accelerate` 與 `bitsandbytes` 已列為核心依賴，因此一般安裝就會一併裝入：

```bash
pip install torch
pip install .
```

若要跑測試：

```bash
pip install '.[dev]'
```

## 5. 驗證

```bash
transcript-polish --help
python -c "import torch; print(torch.cuda.is_available())"
```

若要確認 Quality 模式依賴：

```bash
python -c "import accelerate, bitsandbytes; print(accelerate.__version__, bitsandbytes.__version__)"
```

若要使用自訂 prompt：

```bash
transcript-polish --prompt-config ./prompt-config.json
```

`--prompt-config` 目前使用 JSON 格式。

## 6. repo 內直接執行

如果你還在開發階段，也可以直接跑 repo 內入口：

```bash
chmod +x ./bin/transcript-polish
./bin/transcript-polish --help
./bin/transcript-polish --dir ./transcript
```

## 7. 更新

```bash
source "$HOME/.venvs/transcript-polish/bin/activate"
pip install --upgrade .
```

## 8. 移除

```bash
rm -rf "$HOME/.venvs/transcript-polish"
```
