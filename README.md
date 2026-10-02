# Transcritor de Reunião

Página web (GitHub Pages, sem servidor, sem chave de API, sem custo) que transcreve a fala em texto. O áudio nunca é gravado nem guardado.

- Idiomas: português (Brasil) e inglês (EUA).
- Fontes de áudio: microfone; áudio do computador (aba/sistema, só Chrome/Edge no desktop); ou os dois juntos.
- Motores: reconhecimento do Chrome (só microfone) e Whisper local (transformers.js no navegador, qualquer fonte).
- Recursos: destaques ★, notas digitadas, falantes manuais, glossário, várias reuniões com busca/lixeira/mesclar.
- Saída: modelos de instruções para colar no Claude (ata, vendas, entrevista, aula, mapa mental, tarefas, perguntar) e exportação TXT/MD/SRT/Word/PDF.
- Limites: celular não captura áudio interno; sem separação automática de falantes; pesquisa de referência em `pesquisa-plaud/`.
- Manual de uso: manual.html (também em /manual.html no site).
