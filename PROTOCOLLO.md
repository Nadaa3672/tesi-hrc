# Protocollo dello studio pilota (scritto PRIMA di raccogliere i dati)

Versione 2 – 4 novembre 2026 (prima di raccogliere i dati). Ogni modifica va annotata in fondo, con data e motivo.

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
| Prima | 5 min | compito standard | compito standard | webcam (`--sessione s<n><A/B>_pre --video`) + orologio |
| In mezzo | 5 min | esercizio braccia | riposo seduta | solo orologio |
| Dopo | 5 min | compito standard | compito standard | webcam (`--sessione s<n><A/B>_post --video`) + orologio |

- **Compito standard**: spostare 40 piccoli oggetti, uno alla volta, dal contenitore di sinistra a quello
  di destra e poi di nuovo a sinistra ("un giro" = 40 spostamenti), ripetendo i giri fino a 5 minuti.
  Stessi oggetti, stessi contenitori, stessa posizione sulla scrivania ogni volta.
- **Esercizio (solo A)**: 5 minuti esatti con due bottiglie d'acqua, alternando 30 s di alzate laterali e 30 s
  di alzate frontali fino all'altezza delle spalle, a ritmo costante. **Obiettivo: Borg 14–16 alla fine.**
  Il peso (0,5 o 1 L) e il ritmo si scelgono UNA volta, nella taratura prima della prima sessione, e poi non
  si cambiano più. Ci si ferma subito in caso di dolore (non è un allenamento).
- **Riposo (solo B)**: 5 minuti seduta, braccia appoggiate.

## Calendario

- **Una sola giornata (4 novembre 2026), 8 sessioni: 4 A + 4 B**, nell'ordine bilanciato
  **A B B A – B A A B** (sessioni s1A, s2B, s3B, s4A, s5B, s6A, s7A, s8B). A e B cadono in media alla
  stessa ora del giorno, quindi un cambiamento lento nel corso della giornata (stanchezza generale,
  abitudine al compito) pesa allo stesso modo su A e su B.
- **Pausa di almeno 45–60 minuti** tra una sessione e l'altra. **Regola per ripartire**: Borg al massimo 1 punto
  sopra il valore di inizio giornata e battito a riposo al massimo 5 bpm sopra quello di inizio giornata;
  altrimenti si aspettano altri 15 minuti. Ogni attesa in più si annota.
- Se la giornata non basta: ci si ferma dopo s4 (la prima metà A B B A è già bilanciata) e la seconda metà
  B A A B si fa un altro giorno, alla stessa ora.
- Con 4 + 4 il valore p più basso ottenibile con il test di Mann–Whitney è circa 0,029: il risultato principale
  può essere significativo solo se tutte le sessioni A si separano da tutte le B. Si accetta questo limite per
  fare lo studio in un giorno.

## Regole di registrazione

- Webcam **fissa** per tutto lo studio: stessa posizione, non si tocca tra "prima" e "dopo".
  Inquadratura: busto, braccia, mani e contenitori sempre visibili.
- Orologio sul polso destro, Sensor Logger acceso per tutti i 15 minuti. All'inizio di ogni registrazione
  webcam: **tre scosse forti del polso** davanti alla webcam.
- **SPAZIO** quando si prende il primo oggetto e poi alla fine di ogni giro di 40 spostamenti (serve a misurare
  il tempo per giro). Dopo le scosse iniziali NON si preme SPAZIO. A 5:00 si preme Q, anche a metà giro.
- Borg (6–20) e KSS (1–9) annotati in 4 momenti: prima del compito iniziale, dopo il compito iniziale,
  dopo la fase in mezzo, dopo il compito finale. Si scrivono in `--note` e nel foglio `sessioni_pilota.csv`.
- Stesso abbigliamento (maniche che lascino vedere i polsi), stessa luce, nessun'altra attività faticosa
  per le braccia nell'ora precedente.

## Misure e test decisi in anticipo

**Misura principale** (una sola, per non dover correggere per test multipli):
- variazione **dopo − prima** della **velocità media dei polsi** (`polsi_velocita_ms`, webcam, profondità di MediaPipe).

**Test**: Mann–Whitney a due code tra le 4 variazioni delle sessioni A e le 4 delle sessioni B, α = 0,05.
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

- 4 novembre 2026, prima di raccogliere i dati: da 6 + 6 sessioni in 6 giorni a **4 + 4 in un giorno**
  (ordine A B B A B A A B, pause di 45–60 minuti con regola di recupero), per rispettare la scadenza
  di consegna del 4 dicembre. Conseguenza dichiarata: p minimo 0,029 e sessioni meno indipendenti.
  Peso e ritmo dell'esercizio fissati nella taratura iniziale.
