#!/usr/bin/env python3
"""
Benessere Network - montaggio automatico video YouTube da copione.

Uso (dalla cartella Video/BenessereNetwork):
  python montaggio.py voci  PROGETTO          -> 3 campioni voce da 10 s in PROGETTO/voci_campioni/
  python montaggio.py scegli-voce NOME        -> salva la voce in config.json per i video successivi
  python montaggio.py tutto PROGETTO          -> voce + visual + montaggio + controllo + miniatura + testi
  python montaggio.py voce|visual|monta|controllo|miniatura|testi PROGETTO   -> singoli passaggi
  python montaggio.py escludi PROGETTO ID [ID...]  -> scarta clip/foto Pexels e rifai visual+monta

PROGETTO e' una cartella in progetti/ con dentro copione.txt e progetto.json.
Ogni passaggio usa la cache in PROGETTO/lavoro/: rilanciare e' sicuro e veloce.
Le chiavi si leggono da .env (o dalle variabili d'ambiente): PEXELS_API_KEY, GEMINI_API_KEY.
"""
import base64, json, math, os, re, shutil, subprocess, sys, time, zlib
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
FONT_DIR = ASSETS / "font"
FONT_BOLD = FONT_DIR / "Poppins-Bold.ttf"
FONT_XBOLD = FONT_DIR / "Poppins-ExtraBold.ttf"
CONFIG = BASE / "config.json"
FAKE = os.environ.get("BN_FAKE") == "1"   # collaudo senza chiavi: voce e immagini finte

W, H, FPS = 1920, 1080, 30
VERDE, MENTA, BIANCO, SCURO = "#34925a", "#daf5d5", "#fafafa", "#0f2a19"

try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass


# ---------------------------------------------------------------- utilita'

def cfg():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save_cfg(c):
    CONFIG.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")


def run(cmd, quiet=True):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit(f"Comando fallito: {cmd[0]} ...")
    return r


def ff(*args):
    return run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args])


def durata(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.strip())


def key(name):
    v = os.environ.get(name, "").strip()
    if not v and not FAKE:
        raise SystemExit(f"Manca {name}: inseriscila nel file .env (vedi .env.example).")
    return v


def hexass(h, alpha="00"):
    h = h.lstrip("#")
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts_ass(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ts_yt(t):
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


# ---------------------------------------------------------------- copione

def leggi_copione(prj):
    frasi, sezione = [], ""
    for line in (prj / "copione.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^---\s*(.+?)\s*---$", line.strip())
        if m:
            sezione = m.group(1).strip()
            continue
        m = re.match(r"^(\d+)\.\s*(.+?)\s*\|\|\s*(.+)$", line.strip())
        if m:
            frasi.append({"n": int(m.group(1)), "testo": m.group(2).strip(),
                          "query": [q.strip() for q in m.group(3).split(",") if q.strip()],
                          "sezione": sezione})
    if not frasi:
        raise SystemExit("copione.txt: nessuna frase nel formato 'N. testo || parole chiave'.")
    for i, f in enumerate(frasi):
        f["fine_sezione"] = i == len(frasi) - 1 or frasi[i + 1]["sezione"] != f["sezione"]
    return frasi


def progetto(prj):
    p = prj / "progetto.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def lavoro(prj, *sub):
    d = prj / "lavoro"
    for s in sub:
        d = d / s
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- voce (Gemini TTS)

def tts_model():
    c = cfg()
    if c.get("tts_model"):
        return c["tts_model"]
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                     headers={"x-goog-api-key": key("GEMINI_API_KEY")}, timeout=30)
    r.raise_for_status()
    nomi = [m["name"].split("/")[-1] for m in r.json().get("models", [])
            if "tts" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]
    if not nomi:
        raise SystemExit("Nessun modello TTS disponibile per questa chiave Gemini.")
    nomi.sort(key=lambda n: (0 if "flash" in n else 1, n))  # flash = piano gratuito
    c["tts_model"] = nomi[0]
    save_cfg(c)
    print(f"Modello TTS: {nomi[0]}")
    return nomi[0]


def tts(testo, voce, out_wav):
    """Genera una frase con Gemini TTS, toglie i silenzi iniziali/finali, salva wav 48 kHz mono."""
    if out_wav.exists():
        return
    raw = out_wav.with_suffix(".pcm")
    if FAKE:
        sec = max(1.2, len(testo.split()) * 0.36)
        ff("-f", "lavfi", "-i", f"sine=frequency=220:duration={sec}", "-ar", "48000", "-ac", "1", out_wav)
        return
    c = cfg()
    # i modelli 2.5 seguono lo stile scritto a parole; i 3.x lo leggerebbero ad alta voce: vogliono tag [..]
    prompt = f"{c['tts_stile']}: {testo}" if "2.5" in tts_model() else f"{c['tts_tag']} {testo}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voce}}}}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{tts_model()}:generateContent"
    for tentativo in range(8):
        r = requests.post(url, json=body, headers={"x-goog-api-key": key("GEMINI_API_KEY")}, timeout=180)
        if r.status_code == 200:
            break
        if r.status_code in (429, 500, 502, 503, 504):
            m = re.search(r'"retryDelay":\s*"(\d+)', r.text)
            attesa = int(m.group(1)) + 2 if m else 20 * (tentativo + 1)
            if r.status_code == 429 and "PerDay" in r.text:
                (BASE / "ultimo_429.json").write_text(r.text)
                raise SystemExit("Quota giornaliera Gemini TTS esaurita: rilancia domani, "
                                 "le frasi gia' fatte restano in cache.")
            print(f"  Gemini {r.status_code}, riprovo tra {attesa}s...")
            time.sleep(attesa)
            continue
        raise SystemExit(f"Gemini TTS errore {r.status_code}: {r.text[:500]}")
    else:
        raise SystemExit("Gemini TTS non risponde, riprova piu' tardi.")
    parts = r.json()["candidates"][0]["content"]["parts"]
    data = next(p["inlineData"] for p in parts if "inlineData" in p)
    mime = data.get("mimeType", "")
    raw.write_bytes(base64.b64decode(data["data"]))
    trim = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
            "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")
    m = re.search(r"rate=(\d+)", mime)
    # PCM grezzo (L16;rate=...) oppure file audio completo (es. audio/wav nei modelli piu' recenti)
    ingresso = ["-f", "s16le", "-ar", m.group(1), "-ac", "1"] if m or not mime.startswith("audio/") else []
    if ingresso and not m:
        ingresso[3] = "24000"
    ff(*ingresso, "-i", raw, "-af", trim, "-ar", "48000", "-ac", "1", out_wav)
    raw.unlink()


def cmd_voci(prj):
    frasi = leggi_copione(prj)
    campione = " ".join(f["testo"] for f in frasi[:3])
    out = prj / "voci_campioni"
    out.mkdir(exist_ok=True)
    for v in cfg()["voci_candidate"]:
        wav = out / f"{v}.wav"
        tts(campione, v, wav)
        ff("-i", wav, "-t", "10", "-af", "afade=t=out:st=9.3:d=0.7", "-b:a", "160k", out / f"{v}.mp3")
        wav.unlink()
        print(f"Campione pronto: {out / (v + '.mp3')}")


def gruppi_mancanti(frasi, d, c):
    """Frasi ancora senza voce, raggruppate (consecutive) per farle in una sola richiesta Gemini:
    la quota gratuita conta le richieste, non le frasi."""
    gruppi, g = [], []
    for f in frasi:
        if (d / f"{f['n']:03d}.wav").exists():
            if g:
                gruppi.append(g)
            g = []
            continue
        parole = sum(len(x["testo"].split()) for x in g) + len(f["testo"].split())
        if g and (len(g) >= c.get("tts_frasi_per_richiesta", 5) or parole > c.get("tts_parole_per_richiesta", 75)):
            gruppi.append(g)
            g = []
        g.append(f)
    if g:
        gruppi.append(g)
    return gruppi


def silenzi(wav, soglia="-40dB", minimo=0.12):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", f"silencedetect=n={soglia}:d={minimo}",
                        "-f", "null", "-"], capture_output=True, text=True)
    ini = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    fin = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(ini, fin))


def tts_gruppo(gruppo, voce, d):
    """Una richiesta per piu' frasi (una per riga), poi taglia l'audio nelle pause tra le frasi.
    Il taglio sceglie le pause piu' lunghe vicine al punto atteso (in base ai caratteri) e controlla che
    ogni pezzo abbia un ritmo di lettura plausibile; se qualcosa non torna ritenta, poi frase per frase."""
    testi = [f["testo"] for f in gruppo]
    tmp = d / f"gruppo_{gruppo[0]['n']:03d}.wav"
    for tentativo in range(2):
        tmp.unlink(missing_ok=True)
        tts("\n".join(testi), voce, tmp)
        tot = durata(tmp)
        sil = [(a, b) for a, b in silenzi(tmp) if a > 0.3 and b < tot - 0.3]
        pesi = [len(t) for t in testi]
        attesi = [tot * sum(pesi[:k + 1]) / sum(pesi) for k in range(len(testi) - 1)]
        tagli = scegli_tagli(sil, attesi, tot)
        if tagli:
            bordi = [0.0] + tagli + [tot]
            ritmi = [pesi[i] / max(0.1, bordi[i + 1] - bordi[i]) for i in range(len(testi))]
            medio = sum(pesi) / tot
            if all(0.6 * medio <= r <= 1.6 * medio for r in ritmi):
                trim = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
                        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")
                for i, f in enumerate(gruppo):
                    ff("-ss", f"{bordi[i]:.3f}", "-to", f"{bordi[i + 1]:.3f}", "-i", tmp, "-af", trim,
                       "-ar", "48000", "-ac", "1", d / f"{f['n']:03d}.wav")
                tmp.unlink()
                return True
        print(f"  pause non chiare nel gruppo, {'ritento' if tentativo == 0 else 'passo frase per frase'}...")
    tmp.unlink(missing_ok=True)
    return False


def scegli_tagli(sil, attesi, tot):
    """Programmazione dinamica: un silenzio per ogni confine, in ordine, premiando durata e vicinanza."""
    n, m = len(attesi), len(sil)
    if m < n:
        return None
    punteggio = lambda j, k: (sil[j][1] - sil[j][0]) - 0.15 * abs((sil[j][0] + sil[j][1]) / 2 - attesi[k])
    best = [[-1e9] * m for _ in range(n)]
    da = [[-1] * m for _ in range(n)]
    for j in range(m):
        best[0][j] = punteggio(j, 0)
    for k in range(1, n):
        top, arg = -1e9, -1
        for j in range(m):
            if j > 0 and best[k - 1][j - 1] > top:
                top, arg = best[k - 1][j - 1], j - 1
            if arg >= 0:
                best[k][j], da[k][j] = top + punteggio(j, k), arg
    j = max(range(m), key=lambda x: best[n - 1][x])
    if best[n - 1][j] <= -1e8:
        return None
    scelti = []
    for k in range(n - 1, -1, -1):
        scelti.append(j)
        j = da[k][j]
    return [(sil[x][0] + sil[x][1]) / 2 for x in reversed(scelti)]


def cmd_voce(prj):
    c = cfg()
    if not c.get("voce"):
        raise SystemExit("Nessuna voce scelta: lancia 'voci' e poi 'scegli-voce NOME'.")
    frasi = leggi_copione(prj)
    d = lavoro(prj, "voce")
    for g in gruppi_mancanti(frasi, d, c):
        nomi = ", ".join(str(f["n"]) for f in g)
        print(f"  voce frasi {nomi} (di {len(frasi)})")
        if len(g) > 1 and not FAKE and tts_gruppo(g, c["voce"], d):
            continue
        for f in g:
            tts(f["testo"], c["voce"], d / f"{f['n']:03d}.wav")
    for f in frasi:
        f["durata"] = round(durata(d / f"{f['n']:03d}.wav"), 3)
    (d / "durate.json").write_text(json.dumps({f["n"]: f["durata"] for f in frasi}, indent=1))
    tot = sum(f["durata"] for f in frasi)
    print(f"Voce pronta: {len(frasi)} frasi, {tot:.1f} s di parlato.")


def frasi_con_tempi(prj):
    frasi = leggi_copione(prj)
    dur = json.loads((lavoro(prj, "voce") / "durate.json").read_text())
    c, t = cfg(), 0.0
    for f in frasi:
        f["durata"] = dur[str(f["n"])]
        f["pausa"] = c["pausa_fine_sezione"] if f["fine_sezione"] else c["pausa_frase"]
        f["inizio"] = t
        f["scena"] = f["durata"] + f["pausa"]
        t += f["scena"]
    return frasi


# ---------------------------------------------------------------- piano delle scene

def piano_inquadrature(f, gancio):
    """Divide la frase in inquadrature da 2-3 s (gancio) o 3-5 s (max 6), tagliando sulle pause."""
    c = cfg()
    L = f["scena"]
    ideale = c["durata_gancio"] if gancio else c["durata_ideale"]
    massimo = c["max_gancio"] if gancio else c["max_inquadratura"]
    n = max(1, math.ceil(L / ideale - 0.15))
    while L / n > massimo:
        n += 1
    if n == 1:
        return [L]
    testo = f["testo"]
    # punti di taglio candidati: punteggiatura (preferiti) e fine parola, in secondi
    punt = [(m.end() / len(testo) * f["durata"], 0) for m in re.finditer(r"[,.;:?!]", testo)]
    parole = [(m.start() / len(testo) * f["durata"], 1) for m in re.finditer(r"\s\S", testo)]
    tagli, prec = [], 0.0
    for k in range(1, n):
        target = L * k / n
        best = min(punt + parole, key=lambda p: abs(p[0] - target) + p[1] * 0.6)
        x = best[0] if abs(best[0] - target) < 0.9 else target
        x = min(max(x, prec + 1.4), L - 1.4 * (n - k))
        tagli.append(x)
        prec = x
    bordi = [0.0] + tagli + [L]
    pezzi = [round(b - a, 3) for a, b in zip(bordi, bordi[1:])]
    if max(pezzi) > massimo:  # sicurezza: torna a tagli uguali
        pezzi = [L / n] * n
    return pezzi


# ---------------------------------------------------------------- Pexels

VIETATE = {"logo", "brand", "text", "sign", "letter", "word", "words", "typography", "apple", "iphone",
           "macbook", "nike", "adidas", "coca", "starbucks", "mcdonald", "advert", "billboard",
           "neon", "quote", "banner", "label-logo", "screen-text", "green screen", "chroma", "subscribe",
           "pills", "pill", "medicine", "drugs", "beer", "wine", "alcohol", "cocktail", "cigarette"}


def pexels(prj, tipo, query):
    cache = lavoro(prj, "pexels") / f"{tipo}_{re.sub(r'[^a-z0-9]+', '_', query.lower())}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    if FAKE:
        risultati = [{"id": f"{tipo}-{zlib.crc32(query.encode()) % 10**6}-{i}", "fake": True, "duration": 12,
                      "user": {"name": "Demo", "url": ""}, "url": f"https://www.pexels.com/{query}/{i}",
                      "photographer": "Demo", "photographer_url": ""} for i in range(6)]
    else:
        url = ("https://api.pexels.com/videos/search" if tipo == "video" else "https://api.pexels.com/v1/search")
        r = requests.get(url, params={"query": query, "orientation": "landscape", "per_page": 30,
                                      "size": "medium", "locale": "en-US"},
                         headers={"Authorization": key("PEXELS_API_KEY")}, timeout=30)
        if r.status_code == 429:
            raise SystemExit("Limite orario Pexels raggiunto: riprova tra un'ora (la cache resta).")
        r.raise_for_status()
        risultati = r.json().get("videos" if tipo == "video" else "photos", [])
    cache.write_text(json.dumps(risultati))
    return risultati


def pulito(item):
    testo = (item.get("url", "") + " " + (item.get("alt") or "")).lower().replace("-", " ")
    return not any(re.search(rf"\b{re.escape(v)}\b", testo) for v in VIETATE)


def file_video(v):
    files = [f for f in v.get("video_files", []) if f.get("width") and f.get("height")
             and f["width"] > f["height"] and f["height"] >= 720 and f["width"] <= 2600]
    if not files:
        return None
    return min(files, key=lambda f: (abs(f["height"] - 1080), -f.get("fps", 0) or 0))


def scegli_asset(prj, queries, durata_min, usati, esclusi):
    """Prima video HD a velocita' naturale (rallentati al massimo del 20%), poi foto."""
    for q in queries:
        for v in pexels(prj, "video", q):
            vid = f"v{v['id']}"
            if vid in usati or vid in esclusi or not pulito(v):
                continue
            if v.get("duration", 0) * 1.2 < durata_min + 0.3:
                continue
            fv = {"link": None} if v.get("fake") else file_video(v)
            if not fv:
                continue
            return {"id": vid, "tipo": "video", "link": fv["link"], "durata_clip": v["duration"],
                    "autore": v["user"]["name"], "autore_url": v["user"]["url"], "pagina": v["url"],
                    "query": q, "fake": v.get("fake", False)}
    for q in queries:
        for p in pexels(prj, "foto", q):
            pid = f"f{p['id']}"
            if pid in usati or pid in esclusi or not pulito(p):
                continue
            link = None if p.get("fake") else p["src"]["original"] + "?auto=compress&cs=tinysrgb&w=3840"
            return {"id": pid, "tipo": "foto", "link": link, "autore": p["photographer"],
                    "autore_url": p["photographer_url"], "pagina": p["url"], "query": q,
                    "fake": p.get("fake", False)}
    return None


def scarica(prj, a):
    ext = ".mp4" if a["tipo"] == "video" else ".jpg"
    out = lavoro(prj, "media") / f"{a['id']}{ext}"
    if out.exists():
        return out
    if a.get("fake"):
        if a["tipo"] == "video":
            ff("-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate=30:duration={a['durata_clip']}",
               "-c:v", "libx264", "-preset", "ultrafast", out)
        else:
            img = Image.new("RGB", (3000, 2000), (60 + zlib.crc32(a["id"].encode()) % 150, 120, 90))
            ImageDraw.Draw(img).text((100, 100), a["id"], fill="white")
            img.save(out)
        return out
    with requests.get(a["link"], stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = out.with_suffix(".part")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
        tmp.rename(out)
    return out


def cmd_visual(prj):
    frasi = frasi_con_tempi(prj)
    esclusi = set(json.loads((lavoro(prj) / "esclusi.json").read_text())) \
        if (lavoro(prj) / "esclusi.json").exists() else set()
    prima_sezione = frasi[0]["sezione"]
    c = cfg()
    usati, timeline = set(), []
    for f in frasi:
        gancio = f["sezione"] == prima_sezione
        pezzi = piano_inquadrature(f, gancio)
        t = f["inizio"]
        for j, L in enumerate(pezzi):
            prod = scena_prodotto(prj, f["n"], j, len(pezzi))
            if prod:
                timeline.append({**prod, "frase": f["n"], "inizio": round(t, 3), "durata": round(L, 3)})
                t += L
                continue
            # query in rotazione: la j-esima parola chiave per la j-esima inquadratura
            qs = f["query"][j % len(f["query"]):] + f["query"][:j % len(f["query"])]
            qs = qs + [" ".join(q.split()[:2]) for q in qs]
            a = scegli_asset(prj, qs, L + c["dissolvenza"], usati, esclusi)
            if a and a["tipo"] == "foto" and L > c["max_foto"]:
                # foto: massimo 4 s, quindi divido in piu' foto diverse
                k = math.ceil(L / c["max_foto"])
                sotto = []
                for _ in range(k):
                    b = scegli_asset(prj, qs, 99, usati, esclusi) if sotto else a  # 99 = solo foto
                    if not b:
                        break
                    usati.add(b["id"])
                    sotto.append(b)
                for b in sotto:
                    timeline.append({**b, "frase": f["n"], "inizio": round(t, 3),
                                     "durata": round(L / len(sotto), 3)})
                    t += L / len(sotto)
                continue
            if not a:
                raise SystemExit(f"Nessuna immagine adatta per la frase {f['n']} ({qs[0]}): "
                                 "cambia le parole chiave nel copione.")
            usati.add(a["id"])
            timeline.append({**a, "frase": f["n"], "inizio": round(t, 3), "durata": round(L, 3)})
            t += L
    for i, s in enumerate(timeline):
        if s["tipo"] != "prodotto":
            s["file"] = str(scarica(prj, s).relative_to(prj))
        print(f"  [{i + 1}/{len(timeline)}] frase {s['frase']}: {s['tipo']} {s['id']} "
              f"{s['durata']:.1f}s  '{s['query']}'")
    (lavoro(prj) / "timeline.json").write_text(json.dumps(timeline, indent=1, ensure_ascii=False))
    scrivi_crediti(prj, timeline)
    print(f"Visual pronto: {len(timeline)} inquadrature, nessuna ripetuta.")


def scrivi_crediti(prj, timeline):
    righe = ["CREDITI - immagini e video da Pexels (licenza Pexels, uso gratuito)", ""]
    for s in timeline:
        if s["tipo"] == "prodotto":
            continue
        righe.append(f"Frase {s['frase']:>2} | {s['tipo']:5} | {s['autore']} ({s['autore_url']}) | {s['pagina']}")
    righe += ["", "Font: Poppins (SIL Open Font License)."]
    m = progetto(prj).get("musica_crediti")
    if m:
        righe.append(f"Musica: {m}")
    (prj / "crediti.txt").write_text("\n".join(righe) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- rendering inquadrature

def scena_prodotto(prj, n, j, tot):
    """Inquadratura con l'immagine del prodotto promosso (progetto.json -> "prodotto"):
    {"file": "immagini/x.jpg", "inquadrature": [[18, -1], [19, 0]]}  (frase, indice; -1 = l'ultima)."""
    p = progetto(prj).get("prodotto")
    if not p:
        return None
    for k, (fn, idx) in enumerate(p["inquadrature"]):
        if fn == n and (idx % tot) == j:
            if not (prj / p["file"]).exists():
                raise SystemExit(f"Manca l'immagine del prodotto: {prj / p['file']}")
            return {"id": f"prodotto_{n}_{j}", "tipo": "prodotto", "file": p["file"], "query": "prodotto",
                    "movimento": ["zoom", "scorrimento", "zoom_out"][k % 3]}
    return None


def tela_prodotto(src, out):
    """Prodotto nitido al centro con ombra, sopra la stessa immagine sfocata e scurita (2x per lo zoom)."""
    w2, h2 = W * 2, H * 2
    im = Image.open(src).convert("RGB")
    bg = im.copy()
    r = max(w2 / bg.width, h2 / bg.height)
    bg = bg.resize((int(bg.width * r) + 1, int(bg.height * r) + 1))
    bg = bg.crop(((bg.width - w2) // 2, (bg.height - h2) // 2, (bg.width - w2) // 2 + w2, (bg.height - h2) // 2 + h2))
    bg = bg.filter(ImageFilter.GaussianBlur(60))
    bg = Image.blend(bg, Image.new("RGB", (w2, h2), SCURO), 0.45)
    fg = im.copy()
    r = min(w2 * 0.62 / fg.width, h2 * 0.74 / fg.height)
    fg = fg.resize((int(fg.width * r), int(fg.height * r)), Image.LANCZOS)
    x, y = (w2 - fg.width) // 2, int((h2 - fg.height) * 0.42)
    ombra = Image.new("L", (w2, h2), 0)
    ImageDraw.Draw(ombra).rounded_rectangle([x + 20, y + 40, x + fg.width + 20, y + fg.height + 40], 40, fill=170)
    bg.paste(Image.new("RGB", (w2, h2), "black"), (0, 0), ombra.filter(ImageFilter.GaussianBlur(45)))
    maschera = Image.new("L", fg.size, 0)
    ImageDraw.Draw(maschera).rounded_rectangle([0, 0, fg.width, fg.height], 36, fill=255)
    bg.paste(fg, (x, y), maschera)
    bg.save(out, quality=95)
    return out


def render_inquadratura(prj, s, idx, durata_out):
    out = lavoro(prj, "inquadrature") / f"{idx:03d}_{s['id']}_{durata_out:.2f}.mp4"
    if out.exists():
        return out
    src = prj / s["file"]
    n = max(1, round(durata_out * FPS))
    zoom = cfg()["zoom_video"] if s["tipo"] == "video" else cfg()["zoom_foto"]
    # direzione del movimento alternata per non avere tutte le scene uguali
    dx = ["iw/2-(iw/zoom/2)", "(iw-iw/zoom)*on/{n}", "(iw-iw/zoom)*(1-on/{n})"][idx % 3].format(n=n)
    zp = (f"zoompan=z='1+{zoom}*on/{n}':x='{dx}':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}")
    enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", FPS]
    if s["tipo"] == "video":
        clip = s["durata_clip"]
        lento = max(1.0, durata_out / max(clip - 0.2, 0.1))
        lento = min(lento, 1.2)                       # mai rallentare oltre il 20%
        serve = durata_out / lento
        start = max(0.0, min((clip - serve) * 0.35, clip - serve - 0.05))
        vf = (f"setpts={lento}*(PTS-STARTPTS),fps={FPS},scale={int(W * 1.25)}:{int(H * 1.25)}:"
              f"force_original_aspect_ratio=increase,crop={int(W * 1.25)}:{int(H * 1.25)},{zp},setsar=1")
        ff("-ss", f"{start:.2f}", "-t", f"{serve + 0.1:.2f}", "-i", src, "-vf", vf,
           "-frames:v", n, *enc, out)
    elif s["tipo"] == "prodotto":
        # movimento lento e morbido (ease in-out) sul prodotto: avvicinamento, scorrimento o allontanamento
        tela = tela_prodotto(src, lavoro(prj, "media") / f"{s['id']}_tela.jpg")
        e = f"(0.5-0.5*cos(PI*on/{n}))"
        mv = s.get("movimento", "zoom")
        z = {"zoom": f"1.0+0.12*{e}", "scorrimento": "1.10", "zoom_out": f"1.12-0.12*{e}"}[mv]
        x = f"(iw-iw/zoom)*(0.15+0.7*{e})" if mv == "scorrimento" else "iw/2-(iw/zoom/2)"
        vf = (f"zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},setsar=1")
        ff("-loop", "1", "-framerate", FPS, "-t", f"{durata_out:.2f}", "-i", tela, "-vf", vf,
           "-frames:v", n, *enc, out)
    else:
        vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},{zp},setsar=1")
        ff("-loop", "1", "-framerate", FPS, "-t", f"{durata_out:.2f}", "-i", src, "-vf", vf,
           "-frames:v", n, *enc, out)
    return out


def schermata_finale(prj):
    """Chiamata all'azione di 5 secondi, nei colori del brand."""
    p, c = progetto(prj), cfg()
    png = lavoro(prj) / "finale.png"
    img = Image.new("RGB", (W, H), VERDE)
    d = ImageDraw.Draw(img)
    for y in range(H):  # sfumatura verde -> verde scuro
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(0x34 * (1 - k * .45)), int(0x92 * (1 - k * .45)), int(0x5a * (1 - k * .45))))
    logo = ASSETS / "logo.png"
    y = 120
    if logo.exists():
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((520, 200))
        img.paste(lg, ((W - lg.width) // 2, y), lg)
        y += lg.height + 50
    else:
        f0 = ImageFont.truetype(str(FONT_BOLD), 46)
        d.text((W / 2, y + 40), "BENESSERE NETWORK", font=f0, fill=MENTA, anchor="mm")
        y += 130
    f1 = ImageFont.truetype(str(FONT_XBOLD), 120)
    d.text((W / 2, y + 80), p.get("finale_titolo", "ISCRIVITI AL CANALE"), font=f1, fill=BIANCO,
           anchor="mm", stroke_width=4, stroke_fill=SCURO)
    # bottone stile "iscriviti"
    f2 = ImageFont.truetype(str(FONT_XBOLD), 54)
    btn = p.get("finale_bottone", "ISCRIVITI  +  CAMPANELLA")
    bw = d.textlength(btn, font=f2) + 120
    by = y + 210
    d.rounded_rectangle([(W - bw) / 2, by, (W + bw) / 2, by + 110], radius=55, fill=MENTA)
    d.text((W / 2, by + 55), btn, font=f2, fill=VERDE, anchor="mm")
    f3 = ImageFont.truetype(str(FONT_BOLD), 50)
    yy = by + 190
    for riga in p.get("finale_righe", ["Scrivi nei commenti la tua esperienza",
                                       "Articolo completo: link in descrizione"]):
        d.text((W / 2, yy), riga, font=f3, fill=BIANCO, anchor="mm")
        yy += 80
    img.save(png)
    return {"id": "finale", "tipo": "foto", "file": str(png.relative_to(prj))}


# ---------------------------------------------------------------- sottotitoli

STOP = set("""il lo la i gli le un uno una di a da in con su per tra fra e ed o che chi non ma se
come al allo alla ai agli alle del dello della dei degli delle dal dalla nel nella nei sul sulla
mi ti si ci vi ne è e' sei sono hai ha ho più piu poi già gia anche solo tutto tutti questo quella
quello questa ogni qui li là cosa mai sempre dopo prima ora oggi te tuo tua tuoi tue suo sua""".split())


def parola_chiave(f, override):
    if str(f["n"]) in override:
        return override[str(f["n"])].lower()
    parole = [re.sub(r"[^\wàèéìòù]", "", w) for w in f["testo"].split()]
    parole = [w for w in parole if w and w.lower() not in STOP]
    return max(parole, key=len).lower() if parole else ""


def blocchi(testo, max_char):
    """Spezza la frase in blocchi brevi da sottotitolo, preferendo la punteggiatura."""
    out, cur = [], []
    for w in testo.split():
        prova = " ".join(cur + [w])
        if cur and len(prova) > max_char:
            out.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
            if re.search(r"[,.;:?!]$", w) and len(prova) > max_char * 0.55:
                out.append(" ".join(cur))
                cur = []
    if cur:
        if out and len(" ".join(cur)) < 10:
            out[-1] += " " + " ".join(cur)
        else:
            out.append(" ".join(cur))
    return out


def evidenzia(blocco, kw):
    if not kw:
        return blocco
    pat = re.compile(rf"(?<![\wàèéìòù])({re.escape(kw)}[\wàèéìòù]*)", re.I)
    return pat.sub(lambda m: f"{{\\c{hexass(MENTA)}}}{m.group(1)}{{\\c{hexass(BIANCO)}}}", blocco, count=1)


def scrivi_ass(prj, frasi, totale):
    c, p = cfg(), progetto(prj)
    override = p.get("parole_evidenziate", {})
    etichette = p.get("etichette_sezioni", {})
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Poppins,{c['sottotitoli_size']},{hexass(BIANCO)},{hexass(BIANCO)},{hexass(SCURO)},&H96000000,-1,0,0,0,100,100,0,0,1,6,3,2,160,160,{c['sottotitoli_margine']},1
Style: Sezione,Poppins,44,{hexass(BIANCO)},{hexass(BIANCO)},{hexass(VERDE)},&H00000000,-1,0,0,0,100,100,1,0,3,16,0,7,70,70,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for f in frasi:
        kw = parola_chiave(f, override)
        bl = blocchi(f["testo"], c["sottotitoli_caratteri"])
        tot = sum(len(b) for b in bl)
        t = f["inizio"]
        for b in bl:
            d = f["durata"] * len(b) / tot
            pop = r"{\fscx92\fscy92\t(0,110,\fscx100\fscy100)}"
            ev.append(f"Dialogue: 1,{ts_ass(t)},{ts_ass(t + d - 0.02)},Sub,,0,0,0,,{pop}{evidenzia(b, kw)}")
            t += d
    # etichetta della sezione in alto a sinistra (barra verde del brand)
    sezioni = {}
    for f in frasi:
        s = sezioni.setdefault(f["sezione"], [f["inizio"], 0])
        s[1] = f["inizio"] + f["scena"]
    for nome, (a, b) in sezioni.items():
        lab = etichette.get(nome, nome if nome.upper().startswith("MOSSA") else "")
        if lab:
            ev.append(f"Dialogue: 0,{ts_ass(a + 0.3)},{ts_ass(b)},Sezione,,0,0,0,,{{\\fad(250,250)}}{lab.upper()}")
    out = lavoro(prj) / "sottotitoli.ass"
    out.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------- montaggio

def musica_continua(brano, durata_min, out):
    """Toglie i silenzi ai bordi del brano e lo ripete con le code sovrapposte (dissolvenza incrociata) fino a coprire il video,
    cosi' non ci sono buchi di musica a ogni giro."""
    trim = ("silenceremove=start_periods=1:start_threshold=-50dB,"
            "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse")
    base = out.with_name("musica_base.wav")
    ff("-i", brano, "-af", f"aresample=48000,aformat=channel_layouts=stereo,{trim}", base)
    giro = durata(base)
    xf = min(cfg().get("musica_sovrapposizione", 4.0), giro / 4)
    n = max(1, math.ceil((durata_min - xf) / (giro - xf)))
    if n == 1:
        shutil.copy(base, out)
        return out
    ins = [a for _ in range(n) for a in ("-i", base)]
    fc, prec = "", "[0:a]"
    for i in range(1, n):
        fc += f"{prec}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri[x{i}];"
        prec = f"[x{i}]"
    ff(*ins, "-filter_complex", fc.rstrip(";"), "-map", prec, out)
    return out


def cmd_monta(prj):
    c, p = cfg(), progetto(prj)
    frasi = frasi_con_tempi(prj)
    timeline = json.loads((lavoro(prj) / "timeline.json").read_text())
    F = c["dissolvenza"]
    T = frasi[-1]["inizio"] + frasi[-1]["scena"]
    fin = schermata_finale(prj)
    durate = [s["durata"] for s in timeline] + [c["durata_finale"]]
    # 1) inquadrature renderizzate (ognuna allungata della dissolvenza, tranne la finale)
    files = []
    for i, s in enumerate(timeline + [fin]):
        extra = F if i < len(timeline) else 0
        files.append(render_inquadratura(prj, {**s, "durata_clip": s.get("durata_clip", 0)}, i, durate[i] + extra))
    # 2) catena di dissolvenze + sottotitoli
    ass = scrivi_ass(prj, frasi, T)
    inp, fc, prev, off = [], [], "0:v", 0.0
    for f in files:
        inp += ["-i", f]
    for i in range(1, len(files)):
        off += durate[i - 1]
        fc.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={F}:offset={off:.3f}[x{i}]")
        prev = f"x{i}"
    fontsdir = str(FONT_DIR).replace("\\", "/").replace(":", "\\:")
    assp = str(ass).replace("\\", "/").replace(":", "\\:")
    fc.append(f"[{prev}]ass='{assp}':fontsdir='{fontsdir}',format=yuv420p[v]")
    script = lavoro(prj) / "xfade.txt"
    script.write_text(";\n".join(fc))
    contenuto_v = lavoro(prj) / "contenuto_video.mp4"
    print("  montaggio scene + sottotitoli...")
    ff(*inp, "-filter_complex_script", script, "-map", "[v]", "-c:v", "libx264", "-preset", "medium",
       "-crf", "16", "-r", FPS, contenuto_v)
    totale = T + c["durata_finale"]
    # 3) traccia voce con le pause
    vd = lavoro(prj, "voce")
    lista = vd / "lista.txt"
    righe = []
    for f in frasi:
        pad = vd / f"{f['n']:03d}_pad.wav"
        ff("-i", vd / f"{f['n']:03d}.wav", "-af", f"apad=whole_dur={f['scena']:.3f}", "-ar", "48000", "-ac", "1", pad)
        righe.append(f"file '{pad.name}'")
    lista.write_text("\n".join(righe))
    voce = lavoro(prj) / "voce_completa.wav"
    ff("-f", "concat", "-safe", "0", "-i", lista, "-af", f"apad=whole_dur={totale:.3f}", "-ar", "48000", voce)
    # 4) musica con ducking + loudness -14 LUFS
    brani = sorted([x for x in (BASE / "musiche").glob("*") if x.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")])
    mix = lavoro(prj) / "audio_mix.wav"
    if brani:
        brano = BASE / "musiche" / p["musica"] if p.get("musica") else brani[zlib.crc32(prj.name.encode()) % len(brani)]
        print(f"  musica: {brano.name}")
        brano = musica_continua(brano, totale, lavoro(prj) / "musica_continua.wav")
        fcx = (f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={c['musica_volume']},"
               f"afade=t=in:d=1.5[m];[0:a]aformat=channel_layouts=stereo,asplit=2[v1][v2];"
               f"[m][v1]sidechaincompress=threshold=0.02:ratio=12:attack=20:release=500:makeup=1[md];"
               f"[v2][md]amix=inputs=2:duration=first:normalize=0,"
               f"afade=t=out:st={totale - 2.5:.2f}:d=2.5[a]")
        ff("-i", voce, "-i", brano, "-filter_complex", fcx, "-map", "[a]",
           "-t", f"{totale:.3f}", mix)
    else:
        print("  ATTENZIONE: cartella musiche vuota, video senza musica di sottofondo.")
        ff("-i", voce, "-ac", "2", mix)
    audio = lavoro(prj) / "audio_finale.wav"
    loudnorm(mix, audio, c["lufs"])
    contenuto = lavoro(prj) / "contenuto.mp4"
    ff("-i", contenuto_v, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
       "-b:a", "192k", "-ar", "48000", "-shortest", contenuto)
    # 5) intro intoccabile + contenuto
    intro = ASSETS / c["intro"]
    out = prj / "video.mp4"
    if intro.exists():
        print("  intro + contenuto...")
        ha_audio = bool(run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                             "stream=index", "-of", "csv=p=0", intro]).stdout.strip())
        ia = "[0:a]" if ha_audio else "[ia]"
        pre = "" if ha_audio else f"anullsrc=r=48000:cl=stereo,atrim=0:{durata(intro):.3f}[ia];"
        fcx = (pre + f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
               f"fps={FPS},setsar=1,format=yuv420p[iv];{ia}aresample=48000,aformat=channel_layouts=stereo[ia2];"
               f"[1:a]aformat=channel_layouts=stereo[ca];[iv][ia2][1:v][ca]concat=n=2:v=1:a=1[v][a]")
        ff("-i", intro, "-i", contenuto, "-filter_complex", fcx, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "12M", "-bufsize", "24M",
           "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out)
        durata_intro = durata(intro)
    else:
        print(f"  ATTENZIONE: {intro.name} non trovata in assets/, video senza intro.")
        ff("-i", contenuto, "-c", "copy", "-movflags", "+faststart", out)
        durata_intro = 0.0
    info = {"durata_intro": durata_intro, "durata_totale": durata(out),
            "sezioni": {}}
    for f in frasi:
        info["sezioni"].setdefault(f["sezione"], durata_intro + f["inizio"])
    (lavoro(prj) / "info.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    print(f"Video pronto: {out}  ({info['durata_totale']:.1f} s)")


def loudnorm(src, dst, lufs):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af",
                        f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    ff("-i", src, "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={m['input_i']}:"
       f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
       f"offset={m['target_offset']}:linear=true", "-ar", "48000", dst)


# ---------------------------------------------------------------- controllo qualita'

def cmd_controllo(prj):
    video = prj / "video.mp4"
    d = lavoro(prj, "controllo")
    for x in d.glob("*.jpg"):
        x.unlink()
    ff("-i", video, "-vf", "fps=1/2,scale=384:-2", d / "f_%04d.jpg")
    frame = sorted(d.glob("f_*.jpg"))
    # fogli provini 4x4 (ogni foglio = 32 secondi) per la revisione visiva
    ff("-framerate", "1", "-i", d / "f_%04d.jpg", "-vf",
       "drawtext=fontfile='" + str(FONT_BOLD).replace(":", "\\:") + "':text='%{eif\\:n*2\\:d}s':x=8:y=8:"
       "fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6,tile=4x4:padding=6:color=white",
       d / "provini_%02d.jpg")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                        "blackdetect=d=0.25:pix_th=0.08", "-an", "-f", "null", "-"], capture_output=True, text=True)
    neri = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)
    timeline = json.loads((lavoro(prj) / "timeline.json").read_text())
    ids = [s["id"] for s in timeline]
    doppi = sorted({i for i in ids if ids.count(i) > 1})
    lunghe = [(s["frase"], s["durata"]) for s in timeline
              if s["durata"] > (cfg()["max_foto"] if s["tipo"] == "foto" else cfg()["max_inquadratura"]) + 0.01]
    lufs = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-af", "ebur128=peak=true",
                           "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", lufs)
    rep = [f"Fotogrammi estratti: {len(frame)} (uno ogni 2 s) -> lavoro/controllo/provini_*.jpg",
           f"Fotogrammi neri: {neri or 'nessuno'}",
           f"Clip ripetute: {doppi or 'nessuna'}",
           f"Inquadrature oltre il limite: {lunghe or 'nessuna'}",
           f"Loudness integrata video completo: {m[-1] if m else '?'} LUFS"]
    (d / "report.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))


# ---------------------------------------------------------------- miniatura e testi

def cmd_miniatura(prj):
    p = progetto(prj)
    timeline = json.loads((lavoro(prj) / "timeline.json").read_text())
    scelta = next((i for i, s in enumerate(timeline) if s["frase"] == p.get("miniatura_frase", 2)), 0)
    s = timeline[scelta]
    sfondo = lavoro(prj) / "miniatura_sfondo.jpg"
    src = prj / s["file"]
    if s["tipo"] == "video":
        ff("-ss", f"{min(2.0, s['durata_clip'] / 2):.2f}", "-i", src, "-frames:v", "1", sfondo)
    else:
        shutil.copy(src, sfondo)
    TW, TH = 1280, 720
    bg = Image.open(sfondo).convert("RGB")
    r = max(TW / bg.width, TH / bg.height)
    bg = bg.resize((int(bg.width * r) + 1, int(bg.height * r) + 1), Image.LANCZOS)
    ox = int((bg.width - TW) * p.get("miniatura_allineamento", 0.65))
    bg = bg.crop((ox, (bg.height - TH) // 2, ox + TW, (bg.height - TH) // 2 + TH))
    # velatura verde scura a sinistra per far risaltare la scritta
    vel = Image.new("L", (TW, TH))
    dv = ImageDraw.Draw(vel)
    for x in range(TW):
        dv.line([(x, 0), (x, TH)], fill=int(235 * max(0, 1 - x / (TW * 0.72)) ** 0.8))
    bg = Image.composite(Image.new("RGB", (TW, TH), (16, 52, 30)), bg, vel)
    d = ImageDraw.Draw(bg)
    righe = p.get("miniatura_testo", ["SEMPRE", "STANCO?"])
    y = 70
    for i, riga in enumerate(righe):
        size = 150 if len(riga) <= 8 else 118
        fnt = ImageFont.truetype(str(FONT_XBOLD), size)
        col = MENTA if i == len(righe) - 1 else BIANCO
        d.text((60, y), riga, font=fnt, fill=col, stroke_width=8, stroke_fill=SCURO)
        y += int(size * 1.02)
    badge = p.get("miniatura_badge", "7 MOSSE")
    fb = ImageFont.truetype(str(FONT_XBOLD), 72)
    bw = d.textlength(badge, font=fb) + 70
    d.rounded_rectangle([60, y + 25, 60 + bw, y + 145], radius=24, fill=VERDE, outline=MENTA, width=5)
    d.text((60 + bw / 2, y + 85), badge, font=fb, fill=BIANCO, anchor="mm")
    logo = ASSETS / "logo.png"
    if logo.exists():
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((220, 110))
        bg.paste(lg, (TW - lg.width - 30, TH - lg.height - 25), lg)
    bg.save(prj / "miniatura.jpg", quality=92)
    print(f"Miniatura pronta: {prj / 'miniatura.jpg'}")


def cmd_testi(prj):
    p = progetto(prj)
    info = json.loads((lavoro(prj) / "info.json").read_text())
    nomi = p.get("capitoli", {})
    cap = [(0.0, p.get("capitolo_intro", "Intro"))]
    cap += [(t, nomi.get(sez, sez.title())) for sez, t in info["sezioni"].items()]
    # YouTube: primo capitolo a 0:00 e ogni capitolo di almeno 10 secondi
    if info["durata_intro"] < 10:
        cap = [(0.0, cap[1][1])] + cap[2:]
    fine = info["durata_totale"]
    ok = []
    for i, (t, nome) in enumerate(cap):
        nxt = cap[i + 1][0] if i + 1 < len(cap) else fine
        if ok and nxt - t < 10:
            continue  # troppo corto: resta dentro il capitolo precedente
        ok.append((t, nome))
    capitoli = [f"{ts_yt(t)} {nome}" for t, nome in ok]
    desc = p.get("descrizione", "").replace("{CAPITOLI}", "\n".join(capitoli)).replace("{LINK}", p.get("link", ""))
    tag = tag_youtube(p)
    txt = ["TITOLO", p.get("titolo", ""), "", "DESCRIZIONE", desc, "", "TAG", ", ".join(tag), ""]
    (prj / "titolo-descrizione-tag.txt").write_text("\n".join(txt), encoding="utf-8")
    print(f"Testi pronti: {prj / 'titolo-descrizione-tag.txt'}")
    controllo_seo(prj, p, desc, tag)


MARCHI = ["Benessere Network", "Etna Wellness"]


def _pulisci(t):
    return re.sub(r"\s+", " ", re.sub(r"[#\"<>,]", " ", t)).strip(" -:|!?.").strip()


def tag_youtube(p):
    """Tag in ordine di forza: titolo intero, pezzi del titolo, parola chiave, correlate, ricerche reali
    (intento di ricerca), tag del progetto, marchi in fondo. Max 500 caratteri come conta YouTube
    (le frasi con spazi valgono 2 caratteri in piu' per le virgolette, piu' le virgole)."""
    titolo = _pulisci(p.get("titolo", "").lower())
    pezzi = [_pulisci(x.lower()) for x in re.split(r"[:|\-–—]", p.get("titolo", "")) if len(x.strip()) > 3]
    candidati = [titolo] + pezzi + [p.get("keyword", "")] + p.get("keyword_correlate", []) \
        + p.get("ricerche", []) + p.get("tag", []) + MARCHI
    out, visti, tot = [], set(), 0
    for t in candidati:
        t = _pulisci(t)
        k = t.lower()
        if not t or k in visti or len(t) > 100:
            continue
        costo = len(t) + (2 if " " in t else 0) + (1 if out else 0)
        if tot + costo > 500:
            continue
        out.append(t)
        visti.add(k)
        tot += costo
    return out


def controllo_seo(prj, p, desc, tag):
    """Coerenza articolo <-> parlato <-> titolo <-> descrizione <-> tag. Scrive controllo-seo.txt."""
    norm = lambda x: re.sub(r"\s+", " ", x.lower().replace("&", " e ")).strip()
    kw = norm(p.get("keyword", ""))
    parlato = norm(" ".join(f["testo"] for f in leggi_copione(prj)))
    inizio_parlato = norm(" ".join(f["testo"] for f in leggi_copione(prj)[:3]))
    titolo, d = norm(p.get("titolo", "")), norm(desc)
    tagl = [norm(t) for t in tag]
    righe, problemi = [], 0

    def check(ok, testo):
        nonlocal problemi
        righe.append(("OK   " if ok else "MANCA") + " " + testo)
        problemi += 0 if ok else 1

    if not kw:
        check(False, "keyword principale in progetto.json (campo \"keyword\", la stessa dell'articolo)")
    else:
        check(kw in titolo, f"keyword '{kw}' nel titolo")
        check(kw in d[:200], f"keyword nelle prime 2 righe della descrizione")
        check(kw in inizio_parlato, f"keyword detta nelle prime 3 frasi del video")
        check(parlato.count(kw) >= 2, f"keyword detta almeno 2 volte nel video (ora {parlato.count(kw)})")
        check(kw in tagl, "keyword tra i tag")
        check(("#" + kw.replace(" ", "").replace("&", "")) in d, f"hashtag #{kw.replace(' ', '')} in descrizione")
    check(norm(_pulisci(p.get("titolo", ""))) in tagl, "titolo intero tra i tag")
    for c in p.get("keyword_correlate", []):
        c = norm(c)
        check(c in d or c in parlato, f"correlata '{c}' nella descrizione o nel parlato")
    check(len(p.get("ricerche", [])) >= 3, "almeno 3 ricerche reali (\"come fare a...\", \"come risolvere...\")")
    check(bool(p.get("link")) and p.get("link", "") in desc, "link all'articolo in descrizione")
    tot = sum(len(t) + (2 if " " in t else 0) for t in tag) + max(0, len(tag) - 1)
    righe.append(f"INFO  {len(tag)} tag, {tot}/500 caratteri")
    (prj / "controllo-seo.txt").write_text("\n".join(righe) + "\n", encoding="utf-8")
    print(f"Controllo SEO: {problemi} da sistemare (vedi controllo-seo.txt)")
    for r in righe:
        if r.startswith("MANCA"):
            print("  " + r)


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "scegli-voce":
        c = cfg()
        c["voce"] = sys.argv[2]
        save_cfg(c)
        print(f"Voce salvata: {sys.argv[2]}")
        return
    prj = Path(sys.argv[2])
    if not prj.is_absolute():
        prj = (BASE / "progetti" / prj) if (BASE / "progetti" / prj).exists() else prj.resolve()
    if cmd == "escludi":
        f = lavoro(prj) / "esclusi.json"
        es = set(json.loads(f.read_text())) if f.exists() else set()
        es.update(sys.argv[3:])
        f.write_text(json.dumps(sorted(es)))
        cmd_visual(prj)
        cmd_monta(prj)
        cmd_controllo(prj)
        return
    passi = {"voci": [cmd_voci], "voce": [cmd_voce], "visual": [cmd_visual], "monta": [cmd_monta],
             "controllo": [cmd_controllo], "miniatura": [cmd_miniatura], "testi": [cmd_testi],
             "tutto": [cmd_voce, cmd_visual, cmd_monta, cmd_controllo, cmd_miniatura, cmd_testi]}
    if cmd not in passi:
        raise SystemExit(__doc__)
    for fn in passi[cmd]:
        print(f"== {fn.__name__[4:]} ==")
        fn(prj)


if __name__ == "__main__":
    main()
