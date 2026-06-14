#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${TRANSCRIPT_POLISH_VENV:-$HOME/.venvs/transcript-polish}"

say_step() {
    printf '\n==> %s\n' "$1"
}

ask_environment_action() {
    local answer
    while true; do
        printf '\n虛擬環境已存在：%s\n' "$VENV_DIR"
        printf '  [r] 保留環境並同步套件（預設）\n'
        printf '  [c] 刪除後重新建立\n'
        printf '  [q] 取消安裝\n'
        read -r -p '請選擇 [r/c/q]: ' answer
        answer="${answer:-r}"
        case "$answer" in
            r|R) return 0 ;;
            c|C)
                printf '即將刪除專用虛擬環境 %s。\n' "$VENV_DIR"
                read -r -p '確定重新建立？[y/N] ' answer
                case "$answer" in
                    y|Y|yes|YES)
                        rm -rf -- "$VENV_DIR"
                        return 0
                        ;;
                    *)
                        printf '保留既有環境。\n'
                        return 0
                        ;;
                esac
                ;;
            q|Q)
                printf '安裝已取消。\n'
                exit 0
                ;;
            *) printf '請輸入 r、c 或 q。\n' ;;
        esac
    done
}

printf '%s\n' 'transcript-polish 互動式安裝程序'
printf '%s\n' '--------------------------------'
printf '專案目錄：%s\n' "$REPO_ROOT"
printf '虛擬環境：%s\n' "$VENV_DIR"
printf '%s\n' '一般使用者安裝完成後可直接執行 transcript-polish，不需要手動啟用 venv。'

say_step '步驟 1/4：檢查 Python 與 venv 支援'
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf '錯誤：找不到 %s。請先安裝 Python 3.10 以上版本。\n' "$PYTHON_BIN" >&2
    exit 1
fi

python_version="$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
printf '使用 Python：%s (%s)\n' "$(command -v "$PYTHON_BIN")" "$python_version"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    printf '錯誤：需要 Python 3.10 以上版本，目前為 %s。\n' "$python_version" >&2
    exit 1
fi
if ! "$PYTHON_BIN" -c 'import venv' >/dev/null 2>&1; then
    printf '錯誤：目前 Python 缺少 venv 模組。Ubuntu / WSL 可執行：\n' >&2
    printf '  sudo apt install python3-venv\n' >&2
    exit 1
fi

say_step '步驟 2/4：建立或重用專用虛擬環境'
if [[ -e "$VENV_DIR" ]]; then
    ask_environment_action
fi
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    printf '建立虛擬環境：%s\n' "$VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
else
    printf '重用既有虛擬環境：%s\n' "$VENV_DIR"
fi
VENV_PYTHON="$VENV_DIR/bin/python"

say_step '步驟 3/4：更新安裝工具'
printf '%s\n' '更新 venv 內的 pip、setuptools、wheel；版本已符合時 pip 不會重裝。'
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

if ! "$VENV_PYTHON" -c 'import tomllib' >/dev/null 2>&1; then
    if ! "$VENV_PYTHON" -c 'import tomli' >/dev/null 2>&1; then
        printf '%s\n' 'Python 3.10 沒有內建 tomllib，安裝小型相容套件 tomli 以讀取 pyproject.toml。'
        "$VENV_PYTHON" -m pip install tomli
    fi
fi

say_step '步驟 4/4：讀取 pyproject.toml 並同步專案'
exec "$VENV_PYTHON" "$SCRIPT_DIR/install.py" \
    --repo-root "$REPO_ROOT" \
    --venv-dir "$VENV_DIR"
