# Transcritor de Reunião

Página web (GitHub Pages, sem servidor, sem chave de API, sem custo) que transcreve a fala em texto. O áudio nunca é gravado nem guardado.

- Idiomas: português (Brasil) e inglês (EUA).
- Fontes de áudio: microfone; áudio do computador (aba/sistema, só Chrome/Edge no desktop); ou os dois juntos.
- Motores: reconhecimento do Chrome (só microfone) e Whisper local (transformers.js no navegador, qualquer fonte).
- Reunião online (Meet, Zoom Web, qualquer aba): escolha "Reunião + meu microfone"; as falas saem como "Participantes" (aba) e "Eu" (microfone). Velocidade do Whisper: Tempo real (tiny, ~3 s de atraso), Equilibrado (base) ou Preciso (small).
- ETL ao parar (automático): Extrair (falas com horário/falante) → Transformar (limpeza, turnos, decisões, tarefas, riscos, perguntas, entidades, palavras-chave, capítulos, participação, resumo) → Carregar (pacote .zip com relatório.md, base-de-conhecimento.md, reuniao.json, CSVs, SRT, TXT, MD). Regras locais, sem IA; para ata redigida use o modelo do Claude.
- Recursos: destaques ★, notas digitadas, falantes manuais, glossário, várias reuniões com busca/lixeira/mesclar.
- Saída: modelos de instruções para colar no Claude (ata, vendas, entrevista, aula, mapa mental, tarefas, perguntar) e exportação TXT/MD/SRT/Word/PDF.
- Limites: app Zoom instalado não é captado (use o Zoom Web, zoom.us/wc); no Linux/Mac só áudio de aba; use fones para o microfone não captar a caixa; celular não captura áudio interno; sem separação automática de falantes.
- Manual de uso: manual.html (também em /manual.html no site).
