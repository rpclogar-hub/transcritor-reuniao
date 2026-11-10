"""ETL da reunião (mesma lógica da página web): Extrair, Transformar, Carregar.
Entrada: lista de linhas [{"t": segundos, "f": falante, "s": texto, "k": "fala"|"nota"|"dest", "d": bool}].
Saída: pasta com relatório, base de conhecimento, JSON, CSVs, SRT, TXT e MD."""
import csv, io, json, re, zipfile
from datetime import datetime
from pathlib import Path

STOP = set(("a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre entre até que se como mas mais menos muito muita muitos muitas já não sim também então assim aqui ali lá isso isto esse essa esses essas este esta estes estas aquele aquela eu tu ele ela nós vocês eles elas me te lhe meu minha seu sua nosso nossa dele dela ser estar ter haver fazer ir vai vou vamos foi era são está estão tem têm tinha ainda só pra pro pela pelo quando onde porque qual quais quem tudo todo toda todos todas cada outro outra outros outras coisa coisas gente tipo bom bem agora depois antes hoje ontem amanhã pode podem posso podemos precisa precisamos fazendo falando falar disse acho achei sendo tendo ficar fica ficou fiz vez vezes dessa desse nesse nessa dessas desses mesmo mesma sempre nunca the and for are but not you all can had her was one our out has have been from they will with this that what when your said there their which would about into than them then these those just like very also here some such only over more most other could should").split())
L = r"[^\W\d_]"          # letra
AN = r"[^\W_]"           # letra ou dígito
DIAS = "segunda|terça|quarta|quinta|sexta|sábado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday"

def W(src):
    return re.compile(rf"(?<!{AN})(?:{src})(?!{AN})", re.I)

RE_ACAO = W(r"vou|vamos (?:enviar|mandar|ligar|agendar|marcar|revisar|verificar|preparar|fechar|confirmar|fazer|criar|definir|resolver)|preciso|precisamos|tenho que|temos que|tem que|fica combinado|ficou combinado|fico de|ficamos de|pode (?:enviar|mandar|ligar|revisar|verificar|agendar)|(?:enviar|mandar|ligar|agendar|marcar|revisar|verificar|preparar|fechar|confirmar) (?:o|a|os|as|um|uma|para|pra|com)|prazo|i will|i'll|we will|we'll|we need to|i need to|let's|action item|deadline|follow up|next step|próximo passo|próximos passos")
RE_DECISAO = W(r"decidimos|ficou decidido|decidiu-se|decidido|aprovado|aprovamos|fechado|combinado|vamos (?:com|usar|adotar|seguir|optar|contratar|lançar)|we decided|we agreed|agreed|approved|decision|the decision")
RE_RISCO = W(rf"risco|problema|bloqueio|bloqueado|atraso|atrasar|atrasado|preocupa{L}*|dificuldade|impedimento|risk|blocker|blocked|delay|delayed|issue|concern")
RE_PRAZO = W(rf"hoje|amanhã|depois de amanhã|(?:dia|até) \d{{1,2}}(?:/\d{{1,2}})?|\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?|semana que vem|próxima semana|fim do mês|final do mês|fim da semana|até (?:{DIAS})|(?:na |nesta |nessa |próxima |proxima )?(?:{DIAS})|today|tomorrow|next week|end of (?:the )?(?:day|week|month)|by (?:{DIAS})")

def hhmmss(s):
    s = int(s)
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"

def srt_t(s):
    ms = int(round((s % 1) * 1000)); i = int(s)
    return f"{hhmmss(i)},{ms:03d}"

def npal(t): return len(t.split())

def limpar(s):
    s = re.sub(rf"(?<!{L})(?:ã+h+m*|ahn+|hmm+|uhm+|hum+|éh+|uh+|erm+)(?!{L})[,.]?\s*", "", s, flags=re.I)
    s = re.sub(rf",?\s*(?<!{L})né(?!{L})\??", "", s, flags=re.I)
    s = re.sub(rf"(?<!{L})({L}{{1,12}})(?:\s+\1)+(?!{L})", r"\1", s, flags=re.I)
    s = re.sub(r"\s+", " ", s); s = re.sub(r"\s+([,.!?])", r"\1", s).strip()
    if not s: return ""
    s = s[0].upper() + s[1:]
    return s if re.search(r"[.!?…]$", s) else s + "."

def frases(t): return [x.strip() for x in re.split(r"(?<=[.!?])\s+", t) if len(x.strip()) > 2]
def palavras(t): return [w for w in re.findall(rf"{L}[\w'-]{{3,}}", t.lower()) if w not in STOP and not w[0].isdigit()]
def topo(d, n): return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

PADROES = [
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")), ("link", re.compile(r"https?://[^\s)]+|www\.[^\s)]+", re.I)),
    ("telefone", re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}")),
    ("valor", re.compile(r"(?:R\$|US\$|\$|€)\s?\d[\d.,]*(?:\s?(?:mil|milhões?|milhão|k|mi|bi))?|\d[\d.,]*\s?(?:reais|dólares|euros|dollars)", re.I)),
    ("percentual", re.compile(r"\d+(?:[.,]\d+)?\s?(?:%|por cento|percent)", re.I)),
    ("data", re.compile(rf"\b\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?\b|(?<!{L})dia \d{{1,2}}(?![\w/])", re.I)),
    ("hora", re.compile(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s?h(?:\s?\d{2})?\b", re.I)),
]

def extrair(linhas, decorrido):
    ordem = sorted(range(len(linhas)), key=lambda i: (linhas[i]["t"], i))
    ord_ = [linhas[i] for i in ordem]
    fala = [l for l in ord_ if l.get("k", "fala") == "fala"]
    segs = []
    for i, l in enumerate(fala):
        w = npal(l["s"]); estim = w / 2.5 + 1
        gap = fala[i+1]["t"] - l["t"] if i + 1 < len(fala) else estim
        segs.append({"id": i+1, "inicio": round(l["t"], 1), "fim": round(l["t"] + max(1, min(estim, gap if gap > .5 else estim)), 1),
                     "falante": l.get("f") or "Não identificado", "texto_original": l["s"], "destaque": bool(l.get("d")), "palavras": w})
    return {"segmentos": segs, "notas": [{"t": l["t"], "texto": l["s"]} for l in ord_ if l.get("k") == "nota"],
            "marcados": [l["t"] for l in ord_ if l.get("k") == "dest"]}

def transformar(ex, decorrido):
    segs, ant = [], ""
    for sg in ex["segmentos"]:
        c = limpar(sg["texto_original"])
        if not c or c.lower() == ant: continue
        ant = c.lower()
        segs.append({**{k: sg[k] for k in ("id", "inicio", "fim", "falante", "texto_original", "destaque")}, "texto": c, "palavras": npal(c)})
    turnos = []
    for sg in segs:
        u = turnos[-1] if turnos else None
        if u and u["falante"] == sg["falante"] and sg["inicio"] - u["fim"] < 4:
            u["texto"] += " " + sg["texto"]; u["fim"] = sg["fim"]; u["palavras"] += sg["palavras"]
        else:
            turnos.append({"inicio": sg["inicio"], "fim": sg["fim"], "falante": sg["falante"], "texto": sg["texto"], "palavras": sg["palavras"]})
    tudo = " ".join(s["texto"] for s in segs)
    sents = [{"t": sg["inicio"], "falante": sg["falante"], "texto": f, "destaque": sg["destaque"]} for sg in segs for f in frases(sg["texto"])]

    freq, bi = {}, {}
    toks = palavras(tudo)
    for i, w in enumerate(toks):
        freq[w] = freq.get(w, 0) + 1
        if i: b = toks[i-1] + " " + w; bi[b] = bi.get(b, 0) + 1
    chaves = [{"termo": k, "ocorrencias": v} for k, v in topo(freq, 20)]
    compostos = [{"termo": k, "ocorrencias": v} for k, v in topo(bi, 10) if v > 1]

    ent, visto = [], {}
    def add(tipo, valor, t):
        k = (tipo, valor.lower())
        if k not in visto:
            visto[k] = {"tipo": tipo, "valor": valor, "ocorrencias": 0, "primeira_vez": t}; ent.append(visto[k])
        visto[k]["ocorrencias"] += 1
    for sg in segs:
        for tipo, rx in PADROES:
            for v in rx.findall(sg["texto"]): add(tipo, v.strip(), sg["inicio"])
        for f in frases(sg["texto"]):
            ws = [w for w in re.sub(r'[,;:"()]', " ", f).split() if w]; nome = []
            for i, w in enumerate(ws):
                if i > 0 and re.fullmatch(r"[A-ZÀ-Ý][a-zà-ÿ]{2,}", w) and w.lower() not in STOP: nome.append(w)
                else:
                    if nome: add("nome", " ".join(nome), sg["inicio"])
                    nome = []
            if nome: add("nome", " ".join(nome), sg["inicio"])
    ent.sort(key=lambda e: (e["tipo"], -e["ocorrencias"]))

    quais = lambda rx: [x for x in sents if rx.search(x["texto"])]
    tarefas = []
    for i, x in enumerate(quais(RE_ACAO)):
        pr = RE_PRAZO.search(x["texto"])
        tarefas.append({"n": i+1, "tempo": hhmmss(x["t"]), "responsavel": x["falante"], "acao": x["texto"], "prazo": pr.group(0) if pr else "não definido", "marcada": "sim" if x["destaque"] else "não"})
    decisoes = [{"n": i+1, "tempo": hhmmss(x["t"]), "falante": x["falante"], "decisao": x["texto"]} for i, x in enumerate(quais(RE_DECISAO))]
    riscos = [{"n": i+1, "tempo": hhmmss(x["t"]), "falante": x["falante"], "trecho": x["texto"]} for i, x in enumerate(quais(RE_RISCO))]
    perguntas = [{"n": i+1, "tempo": hhmmss(x["t"]), "falante": x["falante"], "pergunta": x["texto"]} for i, x in enumerate([x for x in sents if x["texto"].endswith("?") and npal(x["texto"]) >= 3])]

    pont = []
    for i, x in enumerate(sents):
        ps = palavras(x["texto"]); sc = sum(freq.get(w, 0) for w in ps) / max(len(ps), 1) ** .5
        if x["destaque"]: sc *= 1.6
        if RE_DECISAO.search(x["texto"]): sc *= 1.4
        if RE_ACAO.search(x["texto"]): sc *= 1.2
        if npal(x["texto"]) < 5: sc *= .3
        pont.append((sc, i, x))
    n_res = min(6, max(2, round(len(sents) / 8)))
    resumo = [x["texto"] for _, _, x in sorted(sorted(pont, key=lambda p: -p[0])[:n_res], key=lambda p: p[1])]

    caps, cur = [], None
    for u in turnos:
        if cur is None or u["inicio"] - cur["inicio"] >= 300 or u["inicio"] - cur["fim"] > 90:
            cur = {"inicio": u["inicio"], "fim": u["fim"], "textos": [], "falantes": {}}; caps.append(cur)
        cur["fim"] = u["fim"]; cur["textos"].append(u["texto"]); cur["falantes"][u["falante"]] = 1
    capitulos = []
    for i, c in enumerate(caps):
        f = {}
        for w in palavras(" ".join(c["textos"])): f[w] = f.get(w, 0) + 1
        ab = (frases(c["textos"][0]) or [""])[0]
        capitulos.append({"n": i+1, "inicio": hhmmss(c["inicio"]), "fim": hhmmss(c["fim"]), "temas": ", ".join(k for k, _ in topo(f, 4)), "falantes": ", ".join(c["falantes"]), "abertura": ab if len(ab) <= 160 else ab[:157] + "..."})

    porf = {}
    for sg in segs:
        f = porf.setdefault(sg["falante"], {"falante": sg["falante"], "segmentos": 0, "palavras": 0, "segundos": 0})
        f["segmentos"] += 1; f["palavras"] += sg["palavras"]; f["segundos"] += sg["fim"] - sg["inicio"]
    tot_s = sum(f["segundos"] for f in porf.values()) or 1
    falantes = sorted([{"falante": f["falante"], "segmentos": f["segmentos"], "palavras": f["palavras"], "tempo_de_fala": hhmmss(f["segundos"]), "participacao": f"{round(f['segundos']/tot_s*100)}%"} for f in porf.values()], key=lambda f: -f["palavras"])
    dur = max(decorrido, segs[-1]["fim"] if segs else 0); totp = sum(s["palavras"] for s in segs)
    estat = {"duracao": hhmmss(dur), "segmentos_brutos": len(ex["segmentos"]), "segmentos_limpos": len(segs), "descartados_na_limpeza": len(ex["segmentos"]) - len(segs),
             "turnos": len(turnos), "palavras": totp, "palavras_por_minuto": round(totp / (dur / 60)) if dur > 0 else 0, "frases": len(sents),
             "tarefas": len(tarefas), "decisoes": len(decisoes), "riscos": len(riscos), "perguntas": len(perguntas),
             "destaques": len(ex["marcados"]) + sum(1 for s in segs if s["destaque"]), "notas": len(ex["notas"])}
    return {"segmentos": segs, "turnos": turnos, "frases": sents, "palavras_chave": chaves, "termos_compostos": compostos, "entidades": ent, "tarefas": tarefas,
            "decisoes": decisoes, "riscos": riscos, "perguntas": perguntas, "resumo": resumo, "capitulos": capitulos, "falantes": falantes, "estatisticas": estat}

def lista(itens, f): return "\n".join(f(i) for i in itens) if itens else "- (nada encontrado)"

def relatorio(titulo, criada, T, ex):
    e = T["estatisticas"]
    nomes = ", ".join(f["falante"] for f in T["falantes"]) or "nenhum"
    marc = [f"- Momento marcado em {hhmmss(t)}" for t in ex["marcados"]] + [f"- ★ [{hhmmss(s['inicio'])}] {s['texto']}" for s in T["segmentos"] if s["destaque"]] + [f"- Nota [{hhmmss(n['t'])}]: {n['texto']}" for n in ex["notas"]]
    return "\n".join([
        f"# Relatório ETL: {titulo}", "", f"Data: {criada:%d/%m/%Y} · Duração: {e['duracao']} · Palavras: {e['palavras']} · Falantes: {nomes}", "",
        "> Gerado automaticamente por regras locais (sem IA). Confira os trechos; para uma ata redigida, cole a transcrição no Claude.", "",
        "## Resumo automático", lista(T["resumo"], lambda x: "- " + x), "",
        "## Decisões", lista(T["decisoes"], lambda x: f"- [{x['tempo']}] " + (x["falante"] + ": " if x["falante"] != "Não identificado" else "") + x["decisao"]), "",
        "## Tarefas e próximos passos", lista(T["tarefas"], lambda x: f"- [{x['tempo']}] {x['acao']} (responsável: {x['responsavel']}; prazo: {x['prazo']})"), "",
        "## Riscos e problemas citados", lista(T["riscos"], lambda x: f"- [{x['tempo']}] {x['trecho']}"), "",
        "## Perguntas em aberto", lista(T["perguntas"], lambda x: f"- [{x['tempo']}] {x['pergunta']}"), "",
        "## Capítulos", lista(T["capitulos"], lambda c: f"- {c['inicio']} a {c['fim']}: {c['temas'] or 'sem tema claro'}" + (f". Começa com: \"{c['abertura']}\"" if c["abertura"] else "")), "",
        "## Palavras-chave", ", ".join(f"{k['termo']} ({k['ocorrencias']})" for k in T["palavras_chave"]) or "(nenhuma)", "",
        "## Entidades (e-mails, links, valores, datas, horas, nomes)", lista(T["entidades"][:60], lambda x: f"- {x['tipo']}: {x['valor']} ({x['ocorrencias']}x)"), "",
        "## Participação", lista(T["falantes"], lambda f: f"- {f['falante']}: {f['palavras']} palavras, {f['tempo_de_fala']} de fala, {f['participacao']}"), "",
        "## Momentos marcados e notas", lista(marc, lambda x: x), "",
        "## Qualidade da carga", f"- Segmentos brutos: {e['segmentos_brutos']} · após limpeza: {e['segmentos_limpos']} · descartados (vazios/repetidos): {e['descartados_na_limpeza']}",
        f"- Ritmo médio: {e['palavras_por_minuto']} palavras por minuto"]) + "\n"

def base_conhecimento(titulo, criada, T):
    partes, atual = [], None
    for u in T["turnos"]:
        if atual is None or atual["pal"] >= 150:
            atual = {"ini": u["inicio"], "fim": u["fim"], "pal": 0, "txt": [], "f": {}}; partes.append(atual)
        atual["fim"] = u["fim"]; atual["pal"] += u["palavras"]
        atual["txt"].append((u["falante"] + ": " if u["falante"] != "Não identificado" else "") + u["texto"]); atual["f"][u["falante"]] = 1
    temas = ", ".join(k["termo"] for k in T["palavras_chave"][:8])
    cab = f"---\ntitulo: {titulo}\ndata: {criada:%Y-%m-%d}\nduracao: {T['estatisticas']['duracao']}\ntemas: {temas}\ntipo: base-de-conhecimento-de-reuniao\n---\n\n# {titulo}\n\nResumo: {' '.join(T['resumo']) or '(sem resumo)'}\n\n"
    return cab + "\n".join(f"## Trecho {i+1} [{hhmmss(p['ini'])} a {hhmmss(p['fim'])}]\nFalantes: {', '.join(p['f'])}\n\n" + "\n\n".join(p["txt"]) + "\n" for i, p in enumerate(partes))

def to_csv(linhas, cols):
    b = io.StringIO(newline="")
    w = csv.writer(b, delimiter=";", lineterminator="\r\n")
    w.writerow([c[1] for c in cols])
    for r in linhas: w.writerow([r.get(c[0], "") for c in cols])
    return "﻿" + b.getvalue()

def linha_txt(l):
    h = f"[{hhmmss(l['t'])}]"
    if l.get("k") == "dest": return f"{h} ★ MOMENTO IMPORTANTE"
    if l.get("k") == "nota": return f"{h} NOTA: {l['s']}"
    return f"{h} {'★ ' if l.get('d') else ''}{l['f'] + ': ' if l.get('f') else ''}{l['s']}"

def srt(linhas):
    ls = [l for l in linhas if l.get("k") != "dest"]
    out = []
    for i, l in enumerate(ls):
        fim = max(l["t"] + 1, min(ls[i+1]["t"], l["t"] + 8)) if i + 1 < len(ls) else l["t"] + 4
        out.append(f"{i+1}\n{srt_t(l['t'])} --> {srt_t(fim)}\n{l['f'] + ': ' if l.get('f') else ''}{'[NOTA] ' if l.get('k') == 'nota' else ''}{l['s']}\n")
    return "\n".join(out)

def markdown(titulo, cab, linhas):
    def f(l):
        if l.get("k") == "dest": return f"- **[{hhmmss(l['t'])}] ★ Momento importante**"
        if l.get("k") == "nota": return f"- **[{hhmmss(l['t'])}] Nota:** {l['s']}"
        return f"- [{hhmmss(l['t'])}] {'★ ' if l.get('d') else ''}{'**' + l['f'] + ':** ' if l.get('f') else ''}{l['s']}"
    return f"# {titulo}\n\n{cab}\n\n" + "\n".join(f(l) for l in linhas) + "\n"

def rodar_etl(titulo, criada, linhas, decorrido, idioma, fonte, destino):
    """Roda E, T e L e grava tudo em destino (pasta + .zip). Devolve (pasta, zip, relatorio)."""
    ex = extrair(linhas, decorrido); T = transformar(ex, decorrido)
    rel = relatorio(titulo, criada, T, ex)
    cab = f"Reunião: {titulo} · Data: {criada:%d/%m/%Y} · Duração aproximada: {T['estatisticas']['duracao']} · Idioma falado: {idioma}"
    dados = {"esquema": "reuniao-etl-v1", "gerado_em": datetime.now().isoformat(timespec="seconds"),
             "reuniao": {"titulo": titulo, "criada": criada.isoformat(timespec="seconds"), "idioma": idioma, "fonte_audio": fonte, "motor": "faster-whisper (local)"},
             "extracao": ex, "transformacao": T}
    C = lambda rows, cols: to_csv(rows, cols)
    arqs = {
        "LEIAME.txt": f"Pacote ETL da reunião \"{titulo}\"\n\nrelatorio.md ........ resumo, decisões, tarefas, riscos, perguntas, capítulos\nbase-de-conhecimento.md  texto em trechos com metadados, pronto para colar em qualquer IA\nreuniao.json ....... tudo em um arquivo estruturado (extração + transformação)\ntranscricao.txt/.md  texto com horários e falantes\nlegendas.srt ....... legendas com tempo\ncsv/*.csv .......... planilhas (separador ponto e vírgula, abre no Excel)\n\nA limpeza remove vícios de fala e repetições; o texto original fica em segmentos.csv (texto_original).\n",
        "relatorio.md": rel, "base-de-conhecimento.md": base_conhecimento(titulo, criada, T),
        "reuniao.json": json.dumps(dados, ensure_ascii=False, indent=2),
        "transcricao.txt": cab + "\n\n" + "\n".join(linha_txt(l) for l in linhas) + "\n",
        "transcricao.md": markdown(titulo, cab, linhas), "legendas.srt": srt(linhas),
        "csv/segmentos.csv": C(T["segmentos"], [("id","id"),("inicio","inicio_s"),("fim","fim_s"),("falante","falante"),("texto","texto"),("texto_original","texto_original"),("destaque","destaque"),("palavras","palavras")]),
        "csv/tarefas.csv": C(T["tarefas"], [("n","n"),("tempo","tempo"),("responsavel","responsavel"),("acao","acao"),("prazo","prazo"),("marcada","marcada_com_estrela")]),
        "csv/decisoes.csv": C(T["decisoes"], [("n","n"),("tempo","tempo"),("falante","falante"),("decisao","decisao")]),
        "csv/riscos.csv": C(T["riscos"], [("n","n"),("tempo","tempo"),("falante","falante"),("trecho","trecho")]),
        "csv/perguntas.csv": C(T["perguntas"], [("n","n"),("tempo","tempo"),("falante","falante"),("pergunta","pergunta")]),
        "csv/entidades.csv": C(T["entidades"], [("tipo","tipo"),("valor","valor"),("ocorrencias","ocorrencias"),("primeira_vez","primeira_vez_s")]),
        "csv/palavras-chave.csv": C(T["palavras_chave"] + T["termos_compostos"], [("termo","termo"),("ocorrencias","ocorrencias")]),
        "csv/capitulos.csv": C(T["capitulos"], [("n","n"),("inicio","inicio"),("fim","fim"),("temas","temas"),("falantes","falantes"),("abertura","abertura")]),
        "csv/falantes.csv": C(T["falantes"], [("falante","falante"),("segmentos","segmentos"),("palavras","palavras"),("tempo_de_fala","tempo_de_fala"),("participacao","participacao")]),
    }
    destino = Path(destino); (destino / "csv").mkdir(parents=True, exist_ok=True)
    for nome, txt in arqs.items(): (destino / nome).write_text(txt, encoding="utf-8")
    zpath = destino.with_suffix(".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, txt in arqs.items(): z.writestr(f"{destino.name}/{nome}", txt)
    return destino, zpath, rel, T["estatisticas"]
