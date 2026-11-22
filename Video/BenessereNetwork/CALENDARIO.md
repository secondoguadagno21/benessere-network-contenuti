# Calendario video Benessere Network (approvato da David il 22/11/2026)

Due video a settimana, MARTEDI e VENERDI, uscita su YouTube alle 9:00 (Europe/Rome) e post Facebook alla stessa ora.
Linea: il catalogo dello shop abbinato al bisogno del periodo. Stile MIX (STILE-MIX.md). Colostro escluso.

## Flusso (regola di David, importanza massima: audio e sottotitoli allineati)
1. Copione + voce: `montaggio.py audio PROGETTO` -> `PROGETTO/audio_per_srt_<progetto>.mp3` (sola voce, tempi del montaggio).
2. L'audio va a David, che rimanda l'SRT. Le pause (`pause_extra`) e il testo NON si cambiano piu' dopo l'audio.
3. Con l'SRT: `sottotitoli.srt` nel progetto, `"sottotitoli_srt": "sottotitoli.srt", "srt_base": "voce"` in progetto.json,
   immagini IA (Canva), `montaggio.py tutto`, controllo provini, miniatura Canva, caricamento programmato alle 9:00
   (`carica_youtube.py PROGETTO --pubblica-alle AAAA-MM-GGT09:00:00+01:00`), sottotitoli CC (stesso SRT),
   post Facebook (Metricool) alla stessa ora, primo commento YouTube dopo l'uscita.

Stati: `da fare` -> `audio pronto` (attesa SRT) -> `SRT ricevuto` -> `programmato` -> `pubblicato`.

| Uscita | Cartella progetto | Tema (bisogno) | Prodotto protagonista | Stato |
|---|---|---|---|---|
| mar 25/11 | 2026-11-25_pelle-secca-inverno | Pelle secca e spenta col freddo | Cofanetto Latte di Cammella e Oro | audio pronto |
| ven 28/11 | 2026-11-28_mani-screpolate-aloe-sos | Mani screpolate, pronto soccorso della pelle | Cofanetto Aloe Vera SOS | audio pronto |
| mar 02/12 | 2026-12-02_energia-dicembre | Arrivare a dicembre senza energie | Vitality Complete Kit | da fare |
| ven 05/12 | 2026-12-05_regali-benessere-40-euro | Regali di benessere sotto i 40 euro | Queen Peach / Cofanetto Aloe SOS | da fare |
| mar 09/12 | 2026-12-09_quanti-caffe-dicembre | "Quanti caffe' bevi a dicembre?" | Caffe' al Ganoderma | da fare |
| ven 12/12 | 2026-12-12_regali-per-lui | Regali per lui | Linea Uomo Aloe + profumi | da fare |
| mar 16/12 | 2026-12-16_pancia-gonfia-cene | Pancia gonfia dopo cene e aperitivi | Enzimi e Paraprobiotici | da fare |
| ven 19/12 | 2026-12-19_abbuffate-natale | Le abbuffate di Natale senza perdere il controllo | Total Complete | da fare |
| mar 23/12 | 2026-12-23_stress-feste | Stress da feste e notti corte | Olii essenziali | da fare |
| mar 30/12 | 2026-12-30_rimettersi-in-sesto | Il giorno dopo: rimettersi in sesto | Detox Basic Aloe 98% | da fare |
| ven 02/01 | 2027-01-02_buoni-propositi | Buoni propositi che durano | Slim Start Pack | da fare |
| mar 06/01 | 2027-01-06_detox-gennaio | Detox di gennaio fatto bene | Enjoy Detox | da fare |
| ven 09/01 | 2027-01-09_meno-carboidrati | Meno carboidrati senza soffrire | Low Carb Power | da fare |
| mar 13/01 | 2027-01-13_ritorno-palestra | Si torna in palestra | Enjoy Detox Sport | da fare |
| ven 16/01 | 2027-01-16_blue-monday | Blue Monday: umore e motivazione | Pack Duo Energia | da fare |
| mar 20/01 | 2027-01-20_viso-freddo | Pelle del viso stressata dal freddo | Vipera Elixir | da fare |
| ven 23/01 | 2027-01-23_pausa-pranzo | Pausa pranzo veloce e sana | Sostituto di pasto | da fare |
| mar 27/01 | 2027-01-27_merenda-17 | Fame nervosa parte 2: la merenda delle 17 | GlyPoint Drops | da fare |

## Regole del copione (dal video GlyPoint del 22/11, approvato)
- Gancio che incuriosisce senza svelare la soluzione; la keyword detta entro i primi 7 secondi.
- Tono umano da networker: consulente, mai venditore. Prodotto come "spalla in piu'", con composizione e modo d'uso
  dalla scheda dello shop; claim solo se autorizzati (Reg. UE 432/2012), avvertenze e invito al medico/dermatologo.
- Grafiche con emoji dove aiutano l'attenzione (❄️ 🔥 ✨ 👇 ✅ ...): TITOLO, PAROLA, ELENCO, NUMERO, BARRATO.
- Chiusura: WhatsApp, poi "Nel primo commento trovi i link: cliente per riceverlo a casa, incaricato se ti piacerebbe
  farlo conoscere e costruirti un'attivita' tutta tua" (mai promesse di guadagno), iscrizione + domanda per i commenti.
- Link: cliente https://etnawellness.com/register?sponsor=159231&tipo=cliente
  incaricato https://etnawellness.com/register?sponsor=6935367&tipo=incaricato
  WhatsApp +39 353 492 5348 https://wa.me/393534925348
