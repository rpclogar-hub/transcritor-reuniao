#!/usr/bin/env python3
"""Transcreve em tempo real o som do Zoom, Google Meet ou de qualquer app (PipeWire) e roda o ETL ao parar (Ctrl+C).
Tudo local: o áudio não é gravado em arquivo nem enviado a ninguém; só o texto é salvo."""
import argparse, difflib, json, queue, re, signal, subprocess, sys, threading, time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
import etl

TAXA = 16000
BLOCO = 1600                      # 0,1 s por bloco (int16 mono)
APPS = {                           # apelidos → pedaços de nome do app no PipeWire
    "zoom": ["zoom"],
    "meet": ["brave", "chrome", "chromium", "edge", "firefox", "opera", "vivaldi"],
    "navegador": ["brave", "chrome", "chromium", "edge", "firefox", "opera", "vivaldi"],
    "teams": ["teams"], "discord": ["discord"], "skype": ["skype"], "telegram": ["telegram"],
}
ALUCINACOES = re.compile(r"^(obrigad[oa][.!]?|legendas? pela comunidade.*|thanks for watching[.!]?|thank you[.!]?|you|\.+|\[.*\]|\(.*\)|♪.*)$", re.I)
PW = "/usr/bin/pw-record"

def hhmmss(s): return etl.hhmmss(s)

# ---------- PipeWire: achar streams do app e ligar ao gravador ----------
def pw_dump():
    try:
        return json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=10).stdout)
    except Exception:
        return []

def achar_streams(dump, termos):
    """Nós Stream/Output/Audio cujo nome/app/binário contém algum termo."""
    achados = []
    for o in dump:
        p = o.get("info", {}).get("props", {})
        if o.get("type") == "PipeWire:Interface:Node" and p.get("media.class") == "Stream/Output/Audio":
            txt = " ".join(str(p.get(k, "")) for k in ("node.name", "application.name", "application.process.binary", "application.id")).lower()
            if any(t in txt for t in termos): achados.append(o["id"])
    return achados

def portas(dump, node_id, direcao):
    r = []
    for o in dump:
        p = o.get("info", {}).get("props", {})
        if o.get("type") == "PipeWire:Interface:Port" and p.get("node.id") == node_id and p.get("port.direction") == direcao:
            r.append(o["id"])
    return r

def no_por_nome(dump, nome):
    for o in dump:
        if o.get("type") == "PipeWire:Interface:Node" and o.get("info", {}).get("props", {}).get("node.name") == nome: return o["id"]
    return None

def ligador(nome_gravador, termos, parar):
    """Liga continuamente (a cada 2 s) as saídas do app ao gravador; pega streams novos e reconectados."""
    ligados = set(); avisado = False
    while not parar.is_set():
        dump = pw_dump(); rec = no_por_nome(dump, nome_gravador)
        if rec:
            entradas = portas(dump, rec, "in")
            for sid in achar_streams(dump, termos):
                for po in portas(dump, sid, "out"):
                    if (po, entradas[0] if entradas else 0) in ligados or not entradas: continue
                    subprocess.run(["pw-link", str(po), str(entradas[0])], capture_output=True)
                    ligados.add((po, entradas[0]))
                    if not avisado: print(f"   (áudio do app conectado: {'/'.join(termos[:2])})", flush=True); avisado = True
        parar.wait(2)

# ---------- Fonte de áudio + segmentação por pausa ----------
class Fonte(threading.Thread):
    def __init__(self, tag, cmd, t0, saida, limiar, parar, tipo):
        super().__init__(daemon=True)
        self.tag, self.cmd, self.t0, self.saida, self.limiar, self.parar, self.tipo = tag, cmd, t0, saida, limiar, parar, tipo
        self.proc = None

    def emitir(self, blocos, ini):
        audio = np.concatenate(blocos).astype(np.float32) / 32768
        self.saida.put((ini, self.tag, audio))

    def run(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        out = self.proc.stdout; buf = bytearray(); cab = True
        pre = deque(maxlen=3); cur = []; ini = 0.0; sil = 0; dentro = False
        while not self.parar.is_set():
            d = out.read(4096)
            if not d: break
            buf += d
            if cab:
                if len(buf) < 44: continue
                del buf[:44]; cab = False
            while len(buf) >= BLOCO * 2:
                blk = np.frombuffer(bytes(buf[:BLOCO * 2]), np.int16); del buf[:BLOCO * 2]
                falando = np.sqrt(np.mean((blk.astype(np.float32) / 32768) ** 2)) > self.limiar
                agora = time.monotonic() - self.t0
                if not dentro:
                    if falando: dentro = True; cur = list(pre) + [blk]; ini = agora - len(cur) * 0.1; sil = 0
                    else: pre.append(blk)
                else:
                    cur.append(blk); sil = 0 if falando else sil + 1
                    dur = len(cur) * 0.1
                    if (sil >= 6 and dur >= 1.0) or dur >= MAX_SEG:
                        self.emitir(cur, ini); cur = []; dentro = False; pre.clear()
                    elif sil >= 6: cur = []; dentro = False
        if dentro and len(cur) >= 10: self.emitir(cur, ini)

    def encerrar(self):
        try:
            if self.proc: self.proc.terminate()
        except Exception: pass

MAX_SEG = 12.0

def main():
    ap = argparse.ArgumentParser(description="Transcrição em tempo real do Zoom/Meet/qualquer app + ETL ao parar.")
    ap.add_argument("--app", default="zoom", help="zoom, meet, navegador, teams, discord, ou parte do nome do app. 'sistema' = todo o som que sai do computador (padrão: zoom)")
    ap.add_argument("--sem-mic", action="store_true", help="não captar o meu microfone")
    ap.add_argument("--modelo", default="small", help="tiny (mais rápido), base, small (padrão), medium (mais preciso, lento)")
    ap.add_argument("--idioma", default="pt", help="pt, en ou auto")
    ap.add_argument("--titulo", default="", help="título da reunião")
    ap.add_argument("--curso", action="store_true", help="modo aula/curso/treinamento longo: capítulos de 15 min, resumo maior, ETL parcial a cada hora")
    ap.add_argument("--recuperar", default="", help="pasta de uma sessão interrompida: roda só o ETL com o que já foi salvo")
    ap.add_argument("--limiar", type=float, default=0.008, help="sensibilidade de voz (menor = mais sensível)")
    a = ap.parse_args()

    if a.recuperar:
        pr = Path(a.recuperar).expanduser(); jl = pr / "linhas.jsonl"
        if not jl.exists(): sys.exit(f"Não achei {jl}")
        ls = [json.loads(x) for x in jl.read_text(encoding="utf-8").splitlines() if x.strip()]
        if not ls: sys.exit("A sessão não tem falas salvas.")
        ls.sort(key=lambda l: l["t"]); cr = datetime.fromtimestamp(jl.stat().st_ctime)
        d, z, rel, est = etl.rodar_etl(a.titulo or f"Reunião recuperada {cr:%d/%m %H:%M}", cr, ls, ls[-1]["t"] + 5, "inglês" if a.idioma == "en" else "português do Brasil", "recuperada", pr / "reuniao_recuperada", a.curso)
        print(f"ETL concluído: {est['palavras']} palavras.\nPasta: {d}\nPacote: {z}"); return
    criada = datetime.now()
    titulo = a.titulo or (f"Curso {criada:%d/%m %H:%M}" if a.curso else f"Reunião {criada:%d/%m %H:%M}")
    pasta = RAIZ / "reunioes" / f"reuniao_{criada:%Y-%m-%d_%H%M}"
    pasta.mkdir(parents=True, exist_ok=True)
    arq_txt = pasta / "transcricao-ao-vivo.txt"; arq_jl = pasta / "linhas.jsonl"
    gloss = []
    gp = AQUI / "glossario.txt"
    if gp.exists():
        for l in gp.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.startswith("#"):
                x, y = [s.strip() for s in l.split("=", 1)]
                if x: gloss.append((re.compile(rf"(?<![^\W_]){re.escape(x)}(?![^\W_])", re.I), y))
    dica = "Glossário: " + ", ".join(y for _, y in gloss) + "." if gloss else None

    print(f"Carregando o modelo de voz '{a.modelo}' (só na primeira vez demora)...", flush=True)
    from faster_whisper import WhisperModel
    modelo = WhisperModel(a.modelo, device="cpu", compute_type="int8", cpu_threads=4)
    lang = None if a.idioma == "auto" else a.idioma

    parar = threading.Event(); fila = queue.Queue(); t0 = time.monotonic()
    fontes = []; linhas = []; lock = threading.Lock()

    base = [PW, "--rate", str(TAXA), "--channels", "1", "--format", "s16"]
    sistema = a.app.lower() in ("sistema", "todos", "tudo")
    if sistema:
        fontes.append(Fonte("Participantes", base + ["-P", "stream.capture.sink=true", "-"], t0, fila, a.limiar, parar, "sistema"))
        origem = "todo o som do computador"
    else:
        termos = APPS.get(a.app.lower(), [a.app.lower()]); nome = f"transcritor-{int(t0)}"
        fontes.append(Fonte("Participantes", base + ["-P", f"node.autoconnect=false", "-P", f"node.name={nome}", "-"], t0, fila, a.limiar, parar, "app"))
        threading.Thread(target=ligador, args=(nome, termos, parar), daemon=True).start()
        origem = f"app: {a.app}"
    if not a.sem_mic:
        fontes.append(Fonte("Eu", base + ["-"], t0, fila, a.limiar, parar, "mic"))
    for f in fontes: f.start()
    print(f"\nOuvindo ({origem}{'' if a.sem_mic else ' + meu microfone'}). Fale/entre na reunião. Ctrl+C para parar e rodar o ETL.\n", flush=True)

    recentes = deque(maxlen=12)
    def aplicar_gloss(t):
        for rx, y in gloss: t = rx.sub(y, t)
        return t

    def worker():
        while True:
            try: ini, tag, audio = fila.get(timeout=0.5)
            except queue.Empty:
                if parar.is_set() and fila.empty(): return
                continue
            if fila.qsize() > 3 and a.modelo != "tiny": print("   (atrasado: use --modelo tiny para acompanhar melhor)", flush=True)
            try:
                trechos, _ = modelo.transcribe(audio, language=lang, beam_size=1, vad_filter=True, condition_on_previous_text=False, initial_prompt=dica)
                txt = " ".join(t.text.strip() for t in trechos).strip()
            except Exception as e:
                print(f"   (falha ao transcrever um trecho: {e})", flush=True); continue
            if not txt or ALUCINACOES.match(txt): continue
            txt = aplicar_gloss(re.sub(r"\s+", " ", txt)); txt = txt[0].upper() + txt[1:]
            # microfone captando o som do alto-falante: descarta "Eu" parecido com "Participantes" recente
            if tag == "Eu" and any(difflib.SequenceMatcher(None, txt.lower(), r.lower()).ratio() > 0.8 and abs(ini - rt) < 10 for rt, r in recentes): continue
            if tag == "Participantes": recentes.append((ini, txt))
            with lock:
                linhas.append({"t": round(ini, 1), "f": tag, "s": txt, "k": "fala"})
                with arq_txt.open("a", encoding="utf-8") as fh: fh.write(f"[{hhmmss(ini)}] {tag}: {txt}\n")
                with arq_jl.open("a", encoding="utf-8") as fj: fj.write(json.dumps(linhas[-1], ensure_ascii=False) + "\n")
            print(f"[{hhmmss(ini)}] {tag}: {txt}", flush=True)

    th = threading.Thread(target=worker); th.start()
    signal.signal(signal.SIGTERM, lambda *_: parar.set())
    signal.signal(signal.SIGINT, lambda *_: parar.set())
    try:
        ultimo_parcial = time.monotonic()
        while not parar.is_set():
            time.sleep(0.3)
            if a.curso and time.monotonic() - ultimo_parcial >= 3600:      # ETL parcial de hora em hora (segurança em sessões longas)
                ultimo_parcial = time.monotonic()
                with lock: copia = sorted(linhas, key=lambda l: l["t"])
                if copia:
                    try: etl.rodar_etl(titulo + " (parcial)", criada, copia, time.monotonic() - t0, "português do Brasil", origem, pasta / "parcial", True); print("   (ETL parcial salvo em 'parcial/')", flush=True)
                    except Exception as e: print(f"   (ETL parcial falhou: {e})", flush=True)
    except KeyboardInterrupt:
        pass
    print("\nParando... terminando o último trecho.", flush=True)
    for f in fontes: f.encerrar()
    time.sleep(0.4); parar.set()
    for f in fontes: f.join(timeout=3)
    th.join()
    dur = time.monotonic() - t0
    if not linhas:
        print("Nenhuma fala captada. Confira se o app estava tocando som (use --app sistema para captar tudo).")
        return
    linhas.sort(key=lambda l: l["t"])
    # eco: o microfone captou o som dos alto-falantes. Remove "Eu" muito parecido com "Participantes" no mesmo momento.
    part = [l for l in linhas if l["f"] == "Participantes"]
    antes = len(linhas)
    linhas = [l for l in linhas if l["f"] != "Eu" or not any(abs(l["t"] - p["t"]) < 12 and difflib.SequenceMatcher(None, l["s"].lower(), p["s"].lower()).ratio() >= 0.55 for p in part)]
    if len(linhas) < antes: print(f"   ({antes - len(linhas)} linha(s) do microfone removidas por serem eco do som da reunião; use fones ou --sem-mic)", flush=True)
    print("Rodando o ETL...", flush=True)
    dest, z, rel, est = etl.rodar_etl(titulo, criada, linhas, dur, "inglês" if a.idioma == "en" else "português do Brasil", origem, pasta / f"reuniao_{criada:%Y-%m-%d_%H%M}", a.curso)
    print(f"\nETL concluído: {est['palavras']} palavras, {est['tarefas']} tarefas, {est['decisoes']} decisões, {est['perguntas']} perguntas.\nPasta: {dest}\nPacote: {z}\n")

if __name__ == "__main__":
    main()
