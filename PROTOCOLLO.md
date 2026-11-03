# Protocollo dello studio pilota (scritto PRIMA di raccogliere i dati)

Versione 1 – 4 novembre 2026. Ogni modifica successiva va annotata in fondo, con data e motivo.

## Obiettivo

Verificare se le misure del framework cambiano dopo un compito che affatica le braccia,
**a parità di tempo trascorso**. Il dataset di Yasar non permette di separare fatica e tempo
(vedi DIARIO, 2 novembre 2026): qui un giorno di controllo dura esattamente quanto un giorno
con fatica, ma senza esercizio.

È uno **studio pilota su un solo soggetto** (l'autrice): serve a verificare il protocollo e il framework
su dati reali. I risultati non sono generalizzabili ad altre persone.

## Condizioni

| Fase | Durata | Condizione A (fatica) | Condizione B (controllo) | Cosa si registra |
| --- | --- | --- | --- | --- |
| Prima | 5 min | compito standard | compito standard | webcam (`--sessione <giorno><A/B>_pre --video`) + orologio |
| In mezzo | 5 min | esercizio braccia | riposo seduta | solo orologio |
| Dopo | 5 min | compito standard | compito standard | webcam (`--sessione <giorno><A/B>_post --video`) + orologio |

- **Compito standard**: spostare 40 piccoli oggetti, uno alla volta, dal contenitore di sinistra a quello
  di destra e poi di nuovo a sinistra ("un giro" = 40 spostamenti), ripetendo i giri fino a 5 minuti.
  Stessi oggetti, stessi contenitori, stessa posizione sulla scrivania ogni volta.
- **Esercizio (solo A)**: 5 minuti esatti con due bottiglie d'acqua (da 0,5 L; se serve 1 L), alternando
  alzate laterali e frontali fino all'altezza delle spalle. **Obiettivo: Borg almeno 14–15 alla fine.**
  Se non si arriva a 14, la volta successiva si aumentano le ripetizioni o il peso.
  Ci si ferma subito in caso di dolore (non è un allenamento).
- **Riposo (solo B)**: 5 minuti seduta, braccia appoggiate.

## Calendario

- **6 giorni, 2 sessioni al giorno** (mattina e pomeriggio, ad almeno 5 ore di distanza): 6 A + 6 B.
- Ordine alternato per bilanciare l'ora del giorno e un eventuale effetto residuo:
  giorno 1 A mattina / B pomeriggio, giorno 2 B / A, giorno 3 A / B, e così via.
- Con 6 + 6 il valore p più basso ottenibile con il test di Mann–Whitney è circa 0,002
  (con 3 + 3 sarebbe 0,10, mai significativo). Se non si riesce, minimo 5 + 5 (p minimo circa 0,008).

## Regole di registrazione

- Webcam **fissa** per tutto lo studio: stessa posizione, non si tocca tra "prima" e "dopo".
  Inquadratura: busto, braccia, mani e contenitori sempre visibili.
- Orologio sul polso destro, Sensor Logger acceso per tutti i 15 minuti. All'inizio di ogni registrazione
  webcam: **tre scosse forti del polso** davanti alla webcam.
- **SPAZIO** all'inizio e alla fine di ogni giro di 40 spostamenti (serve a misurare il tempo per giro).
- Borg (6–20) e KSS (1–9) annotati in 4 momenti: prima del compito iniziale, dopo il compito iniziale,
  dopo la fase in mezzo, dopo il compito finale. Si scrivono in `--note` e nel foglio `sessioni_pilota.csv`.
- Stesso abbigliamento (maniche che lascino vedere i polsi), stessa luce, nessun'altra attività faticosa
  per le braccia nell'ora precedente.

## Misure e test decisi in anticipo

**Misura principale** (una sola, per non dover correggere per test multipli):
- variazione **dopo − prima** della **velocità media dei polsi** (`polsi_velocita_ms`, webcam, profondità di MediaPipe).

**Test**: Mann–Whitney a due code tra le 6 variazioni dei giorni A e le 6 dei giorni B, α = 0,05.
Effetto riportato come differenza tra le mediane e come probabilità di superiorità.

**Controllo della manipolazione**: il Borg dopo la fase in mezzo deve essere più alto nei giorni A che nei B
(stesso test). Se non lo è, l'esercizio non ha affaticato e il risultato principale non è interpretabile.

**Misure secondarie** (esplorative, con correzione di Holm, interpretate con prudenza):
- tempo medio per giro (misura oggettiva di prestazione, dai tempi di SPAZIO);
- rotazione media del polso (`polso_rotazione_media`, orologio);
- elevazione media delle braccia (`braccio_elevazione_media`);
- battito medio (`battito_medio`) e battito subito dopo la fase in mezzo;
- classificazione A-dopo contro B-dopo con `analisi_temporale.py --base persona` (valutazione per sessione).

## Verifica preliminare degli angoli delle braccia (prima della prima sessione)

Registrazione di 25 secondi (`--sessione test_braccia --video`), 5 secondi per posizione:
braccia lungo i fianchi; braccia tese in avanti orizzontali; gomiti piegati a 90° con le braccia lungo i fianchi;
braccia aperte di lato orizzontali; di nuovo lungo i fianchi.
Valori attesi (indicativi): elevazione circa 0°, 90°, 0°, 90°, 0°; gomito circa 180°, 180°, 90°, 180°, 180°.

## Modifiche al protocollo

(nessuna)
