---
name: video-bn
description: Produzione e pubblicazione completa dei video YouTube di Benessere Network (BN) partendo da un articolo di benesserenetwork.com - copione, voce Gemini TTS (Puck), clip Pexels, montaggio con ffmpeg, controllo qualita', miniatura Canva, caricamento su YouTube, video incorporato nell'articolo con miniatura come immagine in evidenza, post Facebook con immagine via Metricool. Usala SEMPRE quando si parla di creare, montare, rifare o pubblicare un video BN / Benessere Network / Etna Wellness, di trasformare un articolo in video, di miniature YouTube del canale, del copione, della voce Puck, di Pexels o di montaggio.py e carica_youtube.py, anche se l'utente non dice "skill" o "video-bn".
---

# Video BN - dall'articolo al video pubblicato ovunque

Il motore e' in `Video/BenessereNetwork/` (leggi anche `PROCEDURA.md`): `montaggio.py` fa voce, visual,
montaggio, controllo, miniatura di riserva e testi YouTube; `carica_youtube.py` pubblica. Qui sotto c'e'
la catena completa e le trappole gia' incontrate. Lo stile e' approvato: non cambiarlo senza che l'utente lo chieda.

Lavora sul ramo indicato dalla sessione, fai commit e push dopo ogni passo che produce file
(voce compresa: il container e' temporaneo e `lavoro/voce/` e' tracciata apposta).

## 0. Input
L'articolo di partenza (URL su benesserenetwork.com, o slug). Se l'utente da' solo un argomento, chiedi
l'articolo: il video nasce SEMPRE da un articolo pubblicato, perche' poi ci viene incorporato.
Leggi l'articolo con WPvibe (`rest_api` GET `/wp/v2/posts?slug=...&context=edit`, sito
`https://benesserenetwork.com`) o con curl sulla pagina pubblica.

## 1. Progetto e copione
Crea `Video/BenessereNetwork/progetti/AAAA-MM-GG_slug/` con:
- `copione.txt` - 2:30-3:30 min (380-480 parole), sezioni `--- GANCIO ---`, `--- MOSSA 1 ---`...,
  `--- CHIAMATA ALL'AZIONE ---`; righe `N. testo || query pexels inglese, seconda query`.
  Tono Borzachiello: frasi brevi, metafore, calore, "tu".
- GANCIO (regola di David): il video si apre col gancio, NON col logo. L'intro col logo parte da sola
  alla fine della sezione GANCIO, quindi il gancio deve durare 15-25 s (circa 45-65 parole, 3-5 frasi).
  Nelle PRIME 20 PAROLE va detta la keyword principale (quella del titolo e della descrizione YouTube),
  e nel resto del gancio almeno una correlata o una ricerca reale. Deve suonare naturale: la keyword dentro
  una domanda o una scena in cui lo spettatore si riconosce, con l'intento di ricerca ("ti chiedi come
  fare a...", "se cerchi come..."), mai un elenco di parole chiave. Alto impatto: domanda, scena concreta,
  promessa del video. Es.: "Stanchezza autunnale: ti svegli e ti sembra di non aver dormito? ..."
- CTA PARLATE (regola di David): una a meta' video, dopo la seconda o terza mossa, breve e calda
  ("Se anche tu ..., scrivimelo nei commenti" oppure "Se ti sta servendo, iscriviti al canale"), e nella
  chiusura: medico se il disturbo e' forte/persistente, iscrizione + campanella, domanda per i commenti.
  Query Pexels: soggetti concreti e visivi ("woman drinking water"), mai concetti astratti, mai pillole,
  alcol, marchi, schermi con testo, "subscribe" (green screen). Il filtro `VIETATE` le scarta comunque.
- `progetto.json` - copia quello dell'ultimo progetto e adatta: `link`, `keyword`, `keyword_correlate`, `ricerche`
  (vedi "SEO YouTube" sotto), `titolo` (max 100 caratteri,
  una parola in MAIUSCOLO), `descrizione` con `{LINK}` e `{CAPITOLI}`, `capitoli` per sezione, `tag`,
  `parole_evidenziate` (una per frase), `miniatura_testo`, `miniatura_badge`, `finale_*`.
  Disclaimer obbligatorio in descrizione: Distributore Indipendente Etna Wellness, integratori non
  sostituiscono una dieta varia, parere medico. Mai claim salutistici oltre quelli autorizzati UE.

### Analisi parole chiave PRIMA di tutto (regola di David)
Il lavoro parte dalle parole chiave, non dal testo. La routine delle bozze fa l'analisi (vidIQ
`vidiq_keyword_research` per volume e concorrenza su YouTube + ricerche reali con intento: "come fare a...",
"come risolvere...", "perche' sono sempre...", "cosa fare se...") e la salva su Airtable (Keyword principale,
Altre keyword, Note "ANALISI KEYWORD"). Su QUELLE parole si costruiscono, nell'ordine: articolo, riassunto,
copione/voce (gancio compreso), titolo, descrizione e tag del video. Se il record non ha l'analisi, falla tu
prima del copione con lo stesso metodo e scrivila nelle Note.

### SEO YouTube: coerenza totale (regola di David)
Articolo, parlato, titolo, descrizione e tag devono raccontare LA STESSA ricerca. In progetto.json:
- `keyword`: la parola chiave principale dell'articolo (Rank Math focus keyword, la prima).
- `keyword_correlate`: le altre 3-4 di Rank Math dell'articolo.
- `ricerche`: 4-6 ricerche reali di chi ha il problema, con intento di ricerca: "come fare a ...",
  "come risolvere ...", "perche' sono sempre ...", "cosa fare se ...", "... cosa fare".
Regole: la keyword nel titolo (meglio all'inizio), nelle prime 2 righe della descrizione, DETTA nelle prime
20 parole del gancio e almeno 2 volte in tutto; le correlate dette o scritte almeno una volta; descrizione che
riassume il video con le stesse parole del parlato; 3 hashtag (il primo = keyword). I tag li costruisce lo
script (`tag_youtube`): titolo intero, pezzi del titolo, keyword, correlate, ricerche, tag, marchi in fondo,
max 500 caratteri. `montaggio.py testi` scrive `controllo-seo.txt`: ogni riga MANCA va sistemata (copione o
descrizione) PRIMA di caricare su YouTube.

## 2. Voce, visual, montaggio
```
cd Video/BenessereNetwork
PEXELS_API_KEY=x GEMINI_API_KEY=x python3 -u montaggio.py tutto PROGETTO
```
Le chiavi Pexels e Gemini le inietta il proxy: basta un valore segnaposto. Lancialo in background e segui il log.
- Voce: Puck, `gemini-3.1-flash-tts-preview`, tag `[warm, confident, energetic, upbeat]` (config.json).
  Quota gratuita: 10 richieste/giorno PER MODELLO; lo script manda 5 frasi per richiesta, quindi
  un video ~7 richieste. Non sprecare richieste in prove. Se finisce la quota: commit+push di
  `lavoro/voce/` e riprendi il giorno dopo. Non mescolare mai due modelli nello stesso video.
- Musica: brani in `musiche/` (Prime_Ascent.mp3), loop con code sovrapposte di 4 s. Sempre BASSA, di
  accompagnamento (`musica_volume` 0.18 in config.json) e abbassata ancora quando parla la voce (ducking).
- Ordine del video: GANCIO -> intro col logo (assets/intro.mp4, intoccabile) -> resto del video. Lo fa lo
  script da solo tagliando a fine sezione GANCIO; il primo capitolo YouTube a 0:00 e' il gancio.
- Il montaggio impiega ~10 min: usa run_in_background e aspetta la notifica (non `pgrep -f` sul
  nome dello script: trova se stesso e non finisce mai).

## 3. Controllo qualita' (obbligatorio prima di pubblicare)
Guarda TUTTI i `lavoro/controllo/provini_*.jpg` e `report.txt`. Scarta con
`python3 montaggio.py escludi PROGETTO vID ...` (ID in `lavoro/timeline.json`; tempo video = inizio per il gancio, inizio + 7,4 s di intro dopo il gancio)
ogni clip con: alcol, pillole/blister/farmaci, marchi o scritte leggibili, green screen, soggetti fuori tema.
Se le sostitute sono ancora sbagliate, cambia le query della frase nel copione e rilancia `escludi`.
Poi manda all'utente un'anteprima 720p (`ffmpeg -vf scale=1280:-2 -crf 28`, file `anteprima_*.mp4`, ignorato da git).

## 4. Miniatura (Canva)
- `create-design` (Canva) formato "YouTube Thumbnail": volto reale molto espressivo che incarna il problema,
  domanda gigante a sinistra (prima riga bianca, seconda gialla #FFE600, contorno nero spesso, font
  condensato), badge verde #34925a con bordo bianco (es. "7 MOSSE"), un'icona-simbolo (batteria scarica,
  sveglia...), alto contrasto, niente altro testo.
- `export-design` jpg 1280x720 qualita' 92.
- Il container NON raggiunge `export-download.canva.com`: passa dal sito. `WPvibe upload_media`
  (site_url benesserenetwork.com, url = link di export Canva, title "Miniatura YouTube <tema>") ->
  restituisce un URL `wp-content/uploads/...` che si scarica con curl. Salvalo come `PROGETTO/miniatura.jpg`
  e tieni l'ID attachment: serve per l'immagine in evidenza e per Facebook.
- Mostra la miniatura all'utente prima di pubblicare.

## 5. YouTube
```
python3 carica_youtube.py PROGETTO --privacy public     # o private/unlisted se l'utente lo chiede
```
Localita' del video SEMPRE "Italia" (regola di David): lo script la imposta da solo con la data di registrazione.
Usa YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN dell'ambiente (scope upload+readonly), canale
"Benessere Network Etna Wellness" (UCsLu6dLbJcKUhMYxS6RehLw). Imposta titolo, descrizione, tag, lingua,
dichiarazione contenuto sintetico (voce IA) e miniatura; scrive `youtube.json` (evita doppioni).
Visibilita': SEMPRE pubblico subito (regola di David). Se lo scope non permette di commentare:
dai all'utente il testo del commento da fissare (domanda + link articolo, tono caldo).

## 6. Articolo
Con WPvibe su benesserenetwork.com (contenuto HTML, non Elementor - verifica comunque):
- Incorpora il video subito dopo il riquadro "In breve" (`aside.risposta-breve` + `</section>`) e prima
  della prima immagine. MAI usare `/wpvibe/v1/content/edit` (regola di David: rovina il codice):
  leggi `content.raw` con GET `/wp/v2/posts/ID?context=edit`, inserisci il blocco in Python sul testo
  esatto (una sola occorrenza, controlla che il blocco non ci sia gia'), poi `POST /wp/v2/posts/ID` con
  TUTTO il contenuto, e rileggi per verificare che il resto sia identico:
  ```html
  <figure class="bn-video" style="margin:2em 0"><div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.15)"><iframe src="https://www.youtube-nocookie.com/embed/VIDEO_ID?rel=0" title="TITOLO" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen style="position:absolute;top:0;left:0;width:100%;height:100%;border:0"></iframe></div><figcaption>Guarda il video: ...</figcaption></figure>
  ```
- Immagine in evidenza = miniatura: `POST /wp/v2/posts/ID {"featured_media": ATTACHMENT_ID}`.
- Verifica sulla pagina pubblica (iframe presente, `og:image` = miniatura).

## 7. Facebook (Metricool)
Brand "Benessere Network by Etna Wellness" (blogId 7246828, timezone Europe/Rome). Pubblicazione
immediata = `createScheduledPost` con data tra 1-2 minuti, `autoPublish: true`.
- POST CON IMMAGINE, non post-link: `media: [URL wp-content della miniatura]`, `facebookData: {"type":"POST"}`.
- Testo: gancio del video in frasi brevi, il valore in 2 righe, domanda per i commenti, e il link
  all'ARTICOLO nella descrizione ("📖 Leggi l'articolo completo: URL"), 3-4 hashtag.
- `firstCommentText`: "▶️ Guarda il video: https://www.youtube.com/watch?v=VIDEO_ID".
- Dopo 2-3 minuti controlla con `getScheduledPosts` che lo stato sia PUBLISHED e dai il `publicUrl`.

## 8. Chiusura
Commit e push di progetto, voce, miniatura, `youtube.json`. Riepilogo all'utente: link YouTube, articolo,
post Facebook, testo del commento da fissare su YouTube, eventuali cose da fare a mano.

## CTA di vendita: aggressive, stile Amazon (regola di David)
Quando si presenta il prodotto da vendere (articolo, scheda, post, descrizione, finale del video), il bottone o
l'invito all'acquisto e' CATTIVO: imperativo, breve, potente, senza dare tempo di pensare.
- Si': "🛒 ACQUISTA ORA", "COMPRA SUBITO →", "SI', LO VOGLIO ADESSO", "CLICCA QUI E ORDINA", "ORDINA ORA
  Energy & Cleanse Set", "PRENDILO SUBITO".
- No: "Vai alla scheda di ...", "Scopri di piu'", "Leggi la scheda", testi descrittivi tiepidi.
- Bottone grande, colore pieno, testo bianco (#FFFFFF !important), nome del prodotto nel bottone o subito sopra.
- Urgenza solo se VERA (promo reale sullo shop con data reale): mai scadenze, scorte limitate o sconti inventati,
  che sono pratica commerciale scorretta e mettono a rischio il sito.

## Riquadri CTA (section.cta-box): SOLO 2 bottoni (regola di David)
Ogni `<section class="cta-box">` (intermedi e finale) ha ESATTAMENTE 2 bottoni, sempre questi:
1. `<a class="btn-wa">SCRIVIMI SU WHATSAPP ORA</a>` (api.whatsapp.com/send?phone=393534925348&text=...)
2. `<a class="btn-cta" href="https://benesserenetwork.com/registrazione-etna-wellness/">REGISTRATI ORA</a>`
Mai bottoni prodotto, shop o negozio dentro un cta-box: i bottoni d'acquisto stanno nella sezione prodotti,
uno sotto ciascun prodotto. Le correzioni si fanno nel contenuto del riquadro, mai con snippet nuovi.

## Riquadri ad alto contrasto (regola di David)
In ogni riquadro (articoli, pagine, copertine, cartelli grafici del video) il testo deve staccare nettamente:
su sfondo scuro testo SEMPRE bianco #FFFFFF e numeri/evidenze verde chiaro #B9F5C9; su sfondo chiaro testo
scuro #0f3d3e. Mai testo scuro o grigio su sfondo scuro. Sul sito c'e' lo snippet WPCode #4417 che forza il
contrasto dei div.callout-numero gia' pubblicati; nei contenuti nuovi il colore va comunque scritto inline.

## Programmazione automatica (routine)
Regola di David: UN GIORNO = UN CONTENUTO COMPLETO. La data di USCITA su Airtable e' il giorno in cui si
prepara e si pubblica tutto; se qualcosa non si chiude in giornata, si pubblica il giorno dopo (mai saltare).
Obiettivo 4 contenuti a settimana, uscite distanziate (es. lun/mer/ven/dom), decise nel calendario Airtable.
Coda Airtable: base appK0PxNveZobZxg9, tabella tblU2fUE8DX2sFSKu. Campi: Argomento fld908dlLxT1DKHtT,
Prodotto fldM0Ao2sYwTz9h7q, Stato fldWxhNd7cSoGgrcM, Link bozza fld86NmYtwE4yS0N9, Note fld0K4E2gXJK5ufeh
(inizia con "USCITA gg/mm/aaaa"). Ora Europe/Rome.
- 05:47 routine "Bozze articoli": analisi keyword + bozza dell'articolo con USCITA = oggi (o scaduta) -> "Bozza pronta".
- 07:47 routine VIDEO: record "Bozza pronta" con USCITA = oggi o scaduta (o "Video in lavorazione" da riprendere).
  Stato "Video in lavorazione" (typecast). Riassunto dell'articolo = copione, passi 2-5 con
  `carica_youtube.py PROGETTO --privacy public`: regola di David, il video va PUBBLICO SUBITO, mai privato o
  programmato. Miniatura: la versione FINALE (identica a YouTube) va su WordPress e il suo attachment nelle Note.
  Note: "VIDEO gg/mm: youtube ID (pubblico), miniatura attachment ID + URL wp-content". Stato "Video pronto".
  MAIL a secondoguadagno21@gmail.com (Gmail) oggetto "✅ Video online: TITOLO" con link YouTube, bozza articolo,
  miniatura, keyword e prime 20 parole del gancio, cose da controllare. Il processo NON aspetta risposte.
- 12:41 routine PUBBLICAZIONE: record "Video pronto" (anche di giorni precedenti), oppure "Bozza pronta" con
  USCITA scaduta da almeno 1 giorno (pubblica senza video). Articolo alle 13:00: video al ~20% del testo (dopo il
  riquadro "In breve", passo 6, POST completo), immagine in evidenza = miniatura, status publish. YouTube: primo
  commento con link all'articolo (senza scope youtube.force-ssl o senza repo, testo nella mail). Facebook alle
  13:00 (passo 7: immagine, link articolo nel testo, link video nel primo commento). Stato "Pubblicato", Note con
  i link, MAIL "🚀 Pubblicato: TITOLO".

## Repository e pulizia
Repository dedicato: secondoguadagno21/benessere-network-contenuti, ramo `main` (ogni routine lavora sul
proprio ramo e pubblica su main a fine giornata). `lavoro/voce/` si versiona SOLO finche' il contenuto non e'
pubblicato (serve a riprendere il giorno dopo); quando il record diventa "Pubblicato", la routine di pubblicazione delle 13:00
fa `git rm -r --cached` + cancella `progetti/<progetto>/lavoro/voce` e committa: restano copione, progetto.json,
miniatura, youtube.json, testi e crediti. Cosi' il repository resta leggero anche con 4 video a settimana.

## Blocchi di rete noti (container)
Bloccati: `shop.benesserenetwork.com`, `export-download.canva.com`, `i.ytimg.com`, `drive.usercontent.google.com`.
Raggiungibili: benesserenetwork.com, API Pexels/Gemini/YouTube. File da Drive: connettore Google Drive
(`download_file_content`, poi decodifica base64 dal file salvato). Immagini da siti bloccati: `WPvibe upload_media`.

## In arrivo
Stacchi grafici / motion graphic (cartelli di sezione a tinta unita, numeri e parole giganti, elenchi
animati ogni 10-15 s): vedi "Prossimo passo" in `PROCEDURA.md`. Non ancora nello script.
