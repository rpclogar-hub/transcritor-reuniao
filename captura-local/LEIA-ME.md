# Captura local: transcrever o som do Zoom (app) e do Meet em tempo real

Programa de terminal (sem servidor). Lê o áudio que sai do app pelo PipeWire, transcreve ao vivo com Whisper (faster-whisper, local) e, ao parar (Ctrl+C), roda o ETL e gera o pacote. O áudio não é gravado nem enviado; só o texto é salvo.

## Como usar
- Zoom (app instalado): clique em "Transcrever reunião - Zoom.desktop" ou `./iniciar.sh --app zoom`
- Google Meet (no navegador): `./iniciar.sh --app meet` (pega Brave, Chrome, Edge, Firefox...)
- Todo o som do computador: `./iniciar.sh --app sistema`
- Outro app: `./iniciar.sh --app discord` (ou parte do nome do app)
- Opções: `--modelo tiny|base|small|medium` (padrão small; tiny é mais rápido e erra mais), `--idioma pt|en|auto`, `--sem-mic`, `--titulo "..."`, `--limiar 0.008` (sensibilidade de voz).
- Participantes = som do app; Eu = seu microfone. Use fones para o microfone não captar a caixa (o programa remove ecos parecidos no final).
- Ctrl+C para parar. Saída em `../reunioes/reuniao_AAAA-MM-DD_HHMM/` (pasta e .zip do ETL; ignorada pelo git).
- `glossario.txt` (opcional, aqui na pasta): uma regra por linha `errado = certo`; os termos também ajudam o Whisper a acertar nomes.

## Requisitos
- PipeWire (`pw-record`, `pw-link`, `pw-dump`) e o venv de `~/Claude/05-local-tools/ditado/venv` (faster-whisper, numpy). Modelos em `~/.cache/huggingface`.

## Limites
- Atraso de alguns segundos; com 4 núcleos, small acompanha pior que tiny enquanto o Zoom está aberto.
- Sem separação de falantes dentro de "Participantes".
- O ETL usa regras locais (sem IA). Para ata redigida, cole `transcricao.txt` no Claude.
