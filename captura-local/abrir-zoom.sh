#!/usr/bin/env bash
# Abre a transcrição ao vivo do app (Zoom) e espera Enter ao final para a janela não fechar sozinha.
cd "$(dirname "$0")" || exit 1
./iniciar.sh --app zoom
echo
read -r -p "Pronto. Enter para fechar"
