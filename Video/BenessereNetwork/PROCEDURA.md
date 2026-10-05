# Procedura video YouTube - Benessere Network

## Preparazione (una volta sola)
- Python 3 + ffmpeg. Librerie: `pip install pillow requests python-dotenv`
- Chiavi in `.env` (copia `.env.example`) oppure come variabili d'ambiente: `PEXELS_API_KEY`, `GEMINI_API_KEY`
- `assets/intro.mp4` = intro ufficiale (mai modificata). `assets/logo.png` = logo (facoltativo, per finale e miniatura)
- `musiche/` = brani senza diritti (mp3/wav)
- Font Poppins gia' incluso in `assets/font/`

## Per ogni nuovo articolo
1. Crea `progetti/AAAA-MM-GG_titolo-articolo/` con:
   - `copione.txt`: sezioni `--- NOME ---` e frasi `N. testo || parole chiave inglesi, altre parole chiave`
   - `immagini/`: l'immagine del prodotto promosso nell'articolo (scaricala dallo shop). In `progetto.json`
     la chiave `prodotto` dice in quali inquadrature mostrarla (es. `[[18, -1], [19, 0]]` = ultima della frase 18,
     prima della 19), con zoom lento e scorrimento
   - `progetto.json`: titolo, descrizione (`{LINK}` e `{CAPITOLI}` vengono riempiti da soli), tag, capitoli,
     parola evidenziata per frase, testo miniatura e schermata finale (copia quello del video precedente)
2. Solo la prima volta: `python montaggio.py voci CARTELLA`, ascolta i campioni, poi `python montaggio.py scegli-voce NOME`
3. `python montaggio.py tutto CARTELLA`
4. Guarda `lavoro/controllo/provini_*.jpg` e `report.txt`. Clip sbagliata? `python montaggio.py escludi CARTELLA v123456`
   (l'ID e' in `lavoro/timeline.json`) e il video si rifa' sostituendola.

## Regole fisse gia' nello script (config.json)
- Intro intera all'inizio, mai tagliata; poi contenuto; poi schermata finale di 5 s
- Gancio: cambio immagine ogni 2-3 s. Resto: 3-5 s, mai oltre 6 s. Foto max 4 s con zoom lento
- Video a velocita' naturale (rallentati al massimo del 20%), nessuna clip ripetuta
- Dissolvenze 0,4 s, sottotitoli Poppins Bold #fafafa con parola chiave #daf5d5, etichette "MOSSA" su barra #34925a
- Musica con ducking sotto la voce, contenuto a -14 LUFS
- Gemini TTS piano gratuito: se finisce la quota giornaliera, rilancia il giorno dopo. Le frasi fatte restano in `lavoro/voce/`: fai commit e push di quella cartella prima di chiudere, cosi' non si perdono

## Stile approvato (video "Stanchezza autunnale", 5 ottobre 2026) - da mantenere
- Voce: Puck con `gemini-3.1-flash-tts-preview`, tag `[warm, confident, energetic, upbeat]`, 5 frasi per richiesta
- Musica: brani in `musiche/` con code sovrapposte di 4 s; sottotitoli Poppins con parola chiave evidenziata
- Copertina: stile Canva (volto espressivo, "DOMANDA?" gigante bianco/giallo con bordo nero, badge verde, icona simbolo)
- Pubblicazione: `python carica_youtube.py PROGETTO --privacy public`, poi video incorporato nell'articolo,
  copertina come immagine in evidenza, post Facebook (Metricool) CON IMMAGINE (la miniatura), link articolo
  nel testo e "Guarda il video" + link YouTube nel primo commento. Catena completa: skill `.claude/skills/video-bn`

## Prossimo passo: stacchi grafici (motion graphic)
1. Cartelli di sezione: a ogni "MOSSA N" schermo a tinta unita (verde #34925a o nero), "MOSSA 2" gigante
   bianco che entra con animazione, sotto il titolo della mossa; 2-2,5 s, con la voce che continua sotto
2. Stacchi ogni 10-15 s sul concetto chiave della frase: fondo pieno o B-roll sfocato/scurito, con
   - frase o parola gigante (es. "10 MINUTI DI LUCE")
   - numero grande con contatore animato (es. "25 OTTOBRE", "-25 EURO")
   - riquadri ed elenchi che compaiono uno alla volta (es. aloe / enzimi / tisana / minerali)
   - grafici semplici (barre, ciclo energia della giornata)
3. Indicazione nel copione: `[CARTELLO ...]` o `[ELENCO ...]` accanto alla frase; lo script genera la grafica
