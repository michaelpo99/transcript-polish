#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${TRANSCRIPT_POLISH_VENV:-$HOME/.venvs/transcript-polish}"
BIN_DIR="${TRANSCRIPT_POLISH_BIN_DIR:-$HOME/bin}"
WRAPPER="$BIN_DIR/transcript-polish"

printf '%s\n' 'transcript-polish 解除安裝程序'
printf '%s\n' '--------------------------------'
printf '將檢查：\n'
printf '  使用者入口：%s\n' "$WRAPPER"
printf '  專用虛擬環境：%s\n' "$VENV_DIR"
printf '%s\n' 'Hugging Face 模型快取不會被刪除。'

read -r -p '確定繼續？[y/N] ' answer
case "$answer" in
    y|Y|yes|YES) ;;
    *)
        printf '解除安裝已取消。\n'
        exit 0
        ;;
esac

if [[ -e "$WRAPPER" || -L "$WRAPPER" ]]; then
    rm -f -- "$WRAPPER"
    printf '已移除：%s\n' "$WRAPPER"
else
    printf '使用者入口不存在，略過：%s\n' "$WRAPPER"
fi

if [[ -d "$VENV_DIR" ]]; then
    rm -rf -- "$VENV_DIR"
    printf '已移除：%s\n' "$VENV_DIR"
else
    printf '虛擬環境不存在，略過：%s\n' "$VENV_DIR"
fi

printf '%s\n' '解除安裝完成。'
printf '%s\n' '如需清理大型模型檔案，請另外檢查 Hugging Face cache；本程序不會自動刪除。'
