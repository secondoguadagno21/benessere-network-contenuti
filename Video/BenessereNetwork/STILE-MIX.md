# Stile MIX - video "interattivo" (clip + immagini IA + cartelli animati)

Stato: in prova sul ramo `stile-mix` (collaudo del 21/11/2026). Lo stile classico resta quello di default.

## Da dove viene
Riferimento scelto da David: "SÁBILA (Aloe Vera): el secreto que los egipcios llamaban inmortal" della
Naturopata Rosy Rodriguez (https://www.youtube.com/watch?v=TkRepI4T8kY), analizzato con Gemini:
36 inquadrature in 4 minuti (una ogni 6-7 s), capitoli numerati che entrano scorrendo, titoli giganti,
contatori, checklist che si spuntano, scritte barrate, parole chiave giganti, immagini IA con zoom lento,
tagli netti, un elemento grafico ogni ~3 s, effetti sonori (pop, whoosh, ding).
Differenza voluta (decisione di David): NESSUNA persona in camera. Al suo posto clip Pexels, immagini IA
(Canva) e cartelli animati. Voce Puck come sempre. Formato orizzontale 16:9.

## Come si attiva
In `progetto.json`: `"stile": "mix"`. Le regole numeriche stanno nel blocco `"mix"` di `config.json`
(transizioni rapide 0,12 s, scorrimento 0,35 s sui capitoli, zoom piu' marcato, effetti al 50%).

## Grafiche nel copione
Dopo le query Pexels, ogni frase puo' avere grafiche separate da `||`:
```
3. Esci dieci minuti appena sveglio. || woman walking park winter || NUMERO: 10 | minuti di luce ogni mattina
```
| Grafica | Cosa fa | Esempio |
|---|---|---|
| `IA: descrizione` | la prima immagine della frase e' l'immagine IA `immagini/ia_N.jpg` | `IA: piatto colorato con uova e verdure` |
| `TITOLO: testo` | cartello con testo gigante, entrata "pop" con glitch | `TITOLO: SEMPRE SPENTO?` |
| `NUMERO: valore \| didascalia` | contatore che gira fino al valore, poi "ding" | `NUMERO: +200 \| componenti` |
| `ELENCO: titolo \| voce; voce; voce` | checklist: le voci si spuntano una alla volta (max 6) | `ELENCO: Il piatto anti-crollo \| Proteine; Verdure; Acqua` |
| `BARRATO: falso \| vero` | la prima frase viene barrata in rosso, la seconda arriva in giallo | `BARRATO: È pigrizia \| È il cambio di stagione` |
| `PAROLA: parole` | etichetta verde gigante sopra l'immagine (non e' un cartello) | `PAROLA: IL PRIMO CAFFÈ` |

Automatici: cartello di capitolo all'inizio di ogni sezione dopo il gancio (non sulla chiamata finale),
con "MOSSA 01" + titolo preso da `capitoli` in progetto.json, entrata e uscita a scorrimento con whoosh;
barra di avanzamento verde in alto; sotto i cartelli a tutto schermo i sottotitoli si nascondono.

## Dosaggio per un video da 2:30-3:30 (regole di partenza, da affinare)
- Gancio: un `TITOLO` con la domanda (o la keyword) + un `IA` o una `PAROLA`.
- Un cartello pieno (`TITOLO`/`NUMERO`/`ELENCO`/`BARRATO`) ogni 15-25 s, mai su due frasi di fila.
- `IA`: 5-7 immagini per video, sulle frasi "concettuali" dove una clip stock sarebbe generica.
- `PAROLA`: 4-8 per video, su numeri e parole chiave (anche la keyword principale).
- Chiamata all'azione finale: niente cartelli, solo immagini + schermata finale.
- Regole di sempre: niente brand, prodotti, prezzi o loghi (regola attuale); claim solo conformi UE.

## Immagini IA (Canva) - catena verificata
1. `python3 montaggio.py ia PROGETTO` -> elenco delle immagini richieste e dei file mancanti.
2. Canva `generate-image`: descrizione in italiano, fotografica e cinematografica, sempre con
   "nessun testo, nessun logo, nessuna marca", `aspectRatio: LANDSCAPE_16_9` -> media id.
3. Canva `create-design` con `references: [media id]`, formato "YouTube Thumbnail", brief "una sola pagina con
   l'immagine a tutta pagina, nessun testo e nessun altro elemento" -> design id.
4. Canva `export-design` jpg 1920x1080 qualita' 92 -> scarica con curl in `PROGETTO/immagini/ia_N.jpg`
   (`export-download.canva.com` e' consentito nell'ambiente SHOP BN dal 21/11/2026).
5. Guarda ogni immagine: niente scritte, mani o volti deformi, marchi. Se non va, rigenera.
Se un'immagine manca, il montaggio usa Pexels e lo scrive nel log.

## Effetti sonori
Sintetizzati da ffmpeg (nessun file scaricato, nessuna licenza): whoosh (capitoli), pop (titoli, parole,
voci di elenco), ding (contatore e checklist), tick (contatore), swish (barrato). Volume: `sfx_volume`.

## Collaudo
`montaggio.py tutto PROGETTO`, poi controllare provini e fotogrammi dei cartelli: testo leggibile, senza
refusi, dentro lo schermo. Anteprima 720p all'utente prima di pubblicare.
