# Plaud Note — relatório consolidado (ETL, 02/10/2026)

Fontes: global.plaud.ai (comparação, trust, intelligence) e plaud.com.br (home, Note, NotePin, como-usar, sobre-nós). Dados em `2-dados-estruturados/`, textos originais em `1-extracao-bruta/`.

## O que é
Linha de gravadores com IA (cartão MagSafe de 30 g ou pin vestível) + app/web/desktop "Plaud Intelligence". Fluxo: **Capturar → Extrair → Utilizar** (grava, transcreve, resume, pergunta, exporta/integra).

## Produtos (US$ global / R$ Brasil)
| Modelo | US$ | R$ site BR | Destaques |
|---|---|---|---|
| Note Pro | 189 | não vendido | 4 mics, 5 m, 50 h, display AMOLED, troca automática chamada/presencial |
| Note | 159 | 1.299 (1.195,08 PIX) | 30 h, 64 GB, 3 m, modo chamada/presencial por botão |
| NotePin S | 179 | 1.699 (esgotado) | 17,4 g, 20 h, Find My |
| NotePin | 159 | 1.399 (esgotado) | 16,7 g, 20 h, colar/pulseira/clip |

## Planos de IA
Starter grátis 300 min/mês · Pro US$6,60/mês (anual) 1.200 min · Unlimited US$19,90/mês. Dispositivo é pago uma vez; a assinatura é o recurso recorrente.

## Capacidades principais
112 idiomas, rótulos de falantes, glossários setoriais, milhares de templates de resumo (3.000+ BR / 10.000+ global), mapa mental, Ask Plaud com citação do áudio, multimodal (fotos/notas/destaques), corte/mescla/importação de áudio, 27+ formatos de exportação, link de compartilhamento (7 dias), Slack/Notion/Drive/Zapier/AutoFlow, API/SDK/MCP, Plaud Desktop (reuniões online sem bot).

## Segurança
ISO 27001/27701, SOC 2 T2, HIPAA, GDPR, EN 18031; TLS 1.2+ e AES-256; sem treino por padrão; LLMs com retenção zero.

## Divergências entre fontes (a verificar)
- Usuários: 2,5 M (global/BR home) × 1 M (sobre-nós BR).
- Templates: 10.000+ × 3.000+.
- Modelos de IA citados no site BR (GPT-4.1, Claude 3.7) estão desatualizados; o site não confirma os atuais.
- Preços em dólar do BR (US$6,60/19,90) — não há cobrança em R$ visível.
- Peso do Note/Armazenamento do Note Pro não constam em todos os textos (campos vazios no CSV).
- Dados de mídia/avaliações vêm da própria marca.

## Aplicação ao projeto `transcritor-reuniao`
Lacunas que o Plaud cobre e vale considerar: rótulos de falantes, templates de resumo por perfil, mapa mental, "pergunte à gravação" com referência ao trecho, glossário personalizado e exportação multi-formato (TXT/SRT/DOCX/PDF/MD).

Limitações da coleta: cobertura sem login (app/web não acessados); páginas de suporte, ROI e "where to buy" não lidas em detalhe; plaud.com.br só acessível via curl (WebFetch retorna 403).
