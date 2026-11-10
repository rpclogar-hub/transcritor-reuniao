#!/usr/bin/env bash
# Uso: ./iniciar.sh [--app zoom|meet|navegador|sistema|<nome>] [--modelo tiny|base|small|medium] [--idioma pt|en|auto] [--sem-mic] [--titulo "..."]
cd "$(dirname "$0")" || exit 1
PY="$HOME/Claude/05-local-tools/ditado/venv/bin/python"
[ -x "$PY" ] || { echo "Falta o venv do ditado (faster-whisper): $PY"; exit 1; }
exec "$PY" transcrever_reuniao.py "$@"
