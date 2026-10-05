#!/usr/bin/env python3
"""
Carica su YouTube il video di un progetto con titolo, descrizione, tag e miniatura.

Uso:  python carica_youtube.py PROGETTO [--privacy public|unlisted|private] [--miniatura FILE]
                                [--pubblica-alle 2026-10-09T17:55:00+02:00]
      python carica_youtube.py PROGETTO --commento "testo"   (primo commento sul video gia' caricato)
      --pubblica-alle: carica privato e YouTube lo rende pubblico da solo a quell'ora (programmato)

Credenziali (OAuth, da variabili d'ambiente o .env): YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,
YOUTUBE_REFRESH_TOKEN (scope youtube.upload). Il risultato va in PROGETTO/youtube.json:
se esiste gia' il video non viene ricaricato (niente doppioni sul canale).
"""
import argparse, json, os, sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass


def token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": os.environ["YOUTUBE_CLIENT_ID"], "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    r.raise_for_status()
    return r.json()["access_token"]


def leggi_testi(prj):
    """Titolo, descrizione e tag da titolo-descrizione-tag.txt (scritto da montaggio.py testi)."""
    blocchi, cur = {}, None
    for riga in (prj / "titolo-descrizione-tag.txt").read_text(encoding="utf-8").splitlines():
        if riga in ("TITOLO", "DESCRIZIONE", "TAG"):
            cur = riga
            blocchi[cur] = []
        elif cur:
            blocchi[cur].append(riga)
    testo = {k: "\n".join(v).strip() for k, v in blocchi.items()}
    return testo["TITOLO"], testo["DESCRIZIONE"], [t.strip() for t in testo["TAG"].split(",") if t.strip()]


def carica(prj, privacy, miniatura, pubblica_alle=None):
    esito = prj / "youtube.json"
    if esito.exists():
        print(f"Gia' caricato: {json.loads(esito.read_text())['url']} (cancella youtube.json per ricaricare)")
        return
    video = prj / "video.mp4"
    titolo, descrizione, tag = leggi_testi(prj)
    if len(titolo) > 100:
        raise SystemExit("Titolo oltre 100 caratteri: accorcialo in progetto.json.")
    h = {"Authorization": f"Bearer {token()}"}
    meta = {"snippet": {"title": titolo, "description": descrizione, "tags": tag, "categoryId": "26",
                        "defaultLanguage": "it", "defaultAudioLanguage": "it"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": True}}  # voce generata con IA: dichiarazione richiesta da YouTube
    if pubblica_alle:
        from datetime import datetime, timezone
        utc = datetime.fromisoformat(pubblica_alle).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        meta["status"].update(privacyStatus="private", publishAt=utc)
        privacy = f"programmato {pubblica_alle}"
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos",
                      params={"uploadType": "resumable", "part": "snippet,status", "notifySubscribers": "true"},
                      headers={**h, "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4",
                               "X-Upload-Content-Length": str(video.stat().st_size)},
                      json=meta, timeout=60)
    if not r.ok:
        raise SystemExit(f"YouTube errore {r.status_code}: {r.text[:800]}")
    print(f"Caricamento {video.stat().st_size / 1e6:.0f} MB...")
    with open(video, "rb") as fh:
        u = requests.put(r.headers["Location"], data=fh, headers={**h, "Content-Type": "video/mp4"}, timeout=3600)
    if not u.ok:
        raise SystemExit(f"Upload fallito {u.status_code}: {u.text[:800]}")
    vid = u.json()["id"]
    url = f"https://www.youtube.com/watch?v={vid}"
    esito.write_text(json.dumps({"id": vid, "url": url, "privacy": privacy}, indent=1))
    print(f"Video caricato: {url}")
    mini = Path(miniatura) if miniatura else prj / "miniatura.jpg"
    if mini.exists():
        t = requests.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                          params={"videoId": vid}, headers={**h, "Content-Type": "image/jpeg"},
                          data=mini.read_bytes(), timeout=120)
        print("Miniatura impostata." if t.ok else f"Miniatura NON impostata ({t.status_code}): {t.text[:400]}")


def commenta(prj, testo):
    """Primo commento sul video (serve lo scope youtube.force-ssl). L'API non permette di fissarlo in alto."""
    vid = json.loads((prj / "youtube.json").read_text())["id"]
    r = requests.post("https://www.googleapis.com/youtube/v3/commentThreads", params={"part": "snippet"},
                      headers={"Authorization": f"Bearer {token()}"}, timeout=60,
                      json={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": testo}}}})
    if r.status_code == 403 and "insufficient" in r.text.lower():
        raise SystemExit("Commento NON pubblicato: il token YouTube non ha lo scope youtube.force-ssl.")
    if not r.ok:
        raise SystemExit(f"Commento NON pubblicato ({r.status_code}): {r.text[:400]}")
    print(f"Commento pubblicato: https://www.youtube.com/watch?v={vid}&lc={r.json()['id']}")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("progetto")
    a.add_argument("--privacy", default="private", choices=["public", "unlisted", "private"])
    a.add_argument("--miniatura")
    a.add_argument("--pubblica-alle", help="ISO 8601 con fuso, es. 2026-10-09T17:55:00+02:00")
    a.add_argument("--commento", help="pubblica solo il primo commento sul video gia' caricato")
    x = a.parse_args()
    prj = Path(x.progetto)
    if not prj.is_absolute():
        prj = (BASE / "progetti" / prj) if (BASE / "progetti" / prj).exists() else prj.resolve()
    if x.commento:
        commenta(prj, x.commento)
    else:
        carica(prj, x.privacy, x.miniatura, x.pubblica_alle)
