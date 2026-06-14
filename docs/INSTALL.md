# 安裝程序

## 1. 安裝系統依賴

在 Ubuntu / WSL：



若要使用 GPU，請先自行準備合適版本的 CUDA / PyTorch。

## 2. 取得專案



或：



## 3. 建立虛擬環境

Requirement already satisfied: pip in /home/michaelpo/.venvs/transcript-polish/lib/python3.12/site-packages (26.1.2)
Requirement already satisfied: setuptools in /home/michaelpo/.venvs/transcript-polish/lib/python3.12/site-packages (81.0.0)
Collecting setuptools
  Using cached setuptools-82.0.1-py3-none-any.whl.metadata (6.5 kB)
Requirement already satisfied: wheel in /home/michaelpo/.venvs/transcript-polish/lib/python3.12/site-packages (0.47.0)
Requirement already satisfied: packaging>=24.0 in /home/michaelpo/.venvs/transcript-polish/lib/python3.12/site-packages (from wheel) (26.2)
Using cached setuptools-82.0.1-py3-none-any.whl (1.0 MB)
Installing collected packages: setuptools
  Attempting uninstall: setuptools
    Found existing installation: setuptools 81.0.0
    Uninstalling setuptools-81.0.0:
      Successfully uninstalled setuptools-81.0.0
Successfully installed setuptools-82.0.1

## 4. 安裝 package

先依你的 CUDA / CPU 環境安裝合適版本的 ，再安裝本專案：



若要使用 ：



## 5. 驗證

usage: transcript-polish [-h] [--file FILE] [--dir DIR] [--model MODEL]
                         [--quantization {none,4bit}]
                         [--replace-dict REPLACE_DICT]
                         [--style-guide STYLE_GUIDE] [--output-dir OUTPUT_DIR]
                         [-f]

使用本地 LLM 整理逐字稿為台灣繁體 Markdown。

options:
  -h, --help            show this help message and exit
  --file FILE           處理單一檔案，僅接受 .txt 或 .md
  --dir DIR             處理指定目錄第一層的 .txt 與 .md
  --model MODEL         指定 Hugging Face 模型名稱
  --quantization {none,4bit}
                        指定模型載入模式，預設為 none
  --replace-dict REPLACE_DICT
                        載入外部強制替換詞彙表
  --style-guide STYLE_GUIDE
                        載入額外 AI 參考指引檔
  --output-dir OUTPUT_DIR
                        指定輸出子目錄名稱或路徑，預設為 formatted
  -f, --force           覆蓋已存在的輸出檔

## 6. repo 內直接執行



## 7. 更新



## 8. 移除


