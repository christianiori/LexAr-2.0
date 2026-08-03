# LexAr

Sito dedicato al lessico nelle commedie aristofanee.

## Avvio locale con API

Il progetto include un backend locale senza dipendenze esterne. All'avvio importa
il TEI degli *Acarnesi* in un database SQLite generato in `data/lexar.sqlite3`.

```powershell
python server.py
```

Apri quindi `http://localhost:8000/` nel browser.

La scheda degli *Acarnesi* include anche un fallback statico del testo, utile
quando il sito viene aperto direttamente dal disco o pubblicato senza backend.
Dopo una modifica al TEI, validalo e rigenera il fallback con:

```powershell
python tools/validate_tei.py
python tools/generate_work_texts.py
```

La trascrizione greca di LexAr resta fondata su Coulon. Gli identificatori dei
frammenti e le coordinate numeriche di riscontro sono applicati dalla mappa
versionata `tools/data/ach-verse-alignment.json`, costruita sul TEI aperto
Hall–Geldart/Perseus senza importarne il testo. L'operazione è idempotente:

```powershell
python tools/number_ach_verses.py
python tools/validate_tei.py
python tools/generate_work_texts.py
```

Se cambia il flusso greco, la mappa va ricostruita e revisionata prima di
riapplicarla:

```powershell
python tools/build_ach_verse_alignment.py C:\percorso\al\tei-perseus.xml
```

Il riferimento digitale è
`tlg0019.tlg001.perseus-grc2` della Perseus Digital Library. Le coordinate non
vanno presentate come collazione integrale della lineazione Coulon: i crossover
restano espressi con più URI CTS e i vv. 1202 e 1206 come lacune.

## Pilot metrico

La personalizzazione TEI di LexAr è documentata in `odd/lexar.odd`. Il pilot
metrico degli *Acarnesi* copre i vv. 1–46 e usa come superficie di revisione il
sidecar versionato `tools/data/ach-metrics.json`: ogni scansione è ancorata agli
`xml:id` dei frammenti e accompagnata da stato, certezza, responsabilità e
fonti. Le annotazioni sono proposte di lavoro, non scansioni già verificate.
Nel lettore i casi standard con scansione presente e certezza media mostrano
soltanto la notazione: l'assenza di un avviso non equivale allo stato
`verified`. I casi a bassa certezza conservano invece l'etichetta «da
verificare»; il nome del metro resta visibile soltanto per l'ipotesi anomala
del v. 43.

La notazione sorgente usa `-` per la lunga, `u` per la breve, `x` per l'anceps,
`|` per il confine di piede e `||` per una cesura editoriale. Nei versi divisi
fra più battute, `real` contiene soltanto la porzione del frammento corrente.
I vv. 20 e 37 e l'ipotesi alternativa del v. 43 conservano volutamente lo
schema senza `real`, perché la scansione richiede ancora una decisione umana.

Dopo una modifica alla mappa metrica o alla numerazione:

```powershell
python tools/number_ach_verses.py
python tools/apply_ach_metrics.py
python tools/apply_ach_metrics.py --check
python tools/validate_tei.py
python tools/generate_work_texts.py
```

`number_ach_verses.py` gestisce soltanto coordinate e identificatori e preserva
gli attributi metrici. Il validatore controlla anche copertura del pilot, firme
strutturali, puntatori TEI e corrispondenza fra sidecar e `xml/ach.xml`.

## Deploy su Render

La configurazione in `render.yaml` crea un Web Service Python e usa
`/api/health` come controllo di integrità. Render assegna la variabile `PORT`,
che il server legge automaticamente. Il database SQLite viene ricreato dal TEI
ad ogni avvio: finché LexAr resta in sola lettura non richiede un disco
persistente. Prima di aggiungere utenti o annotazioni condivise, sarà necessario
un database persistente (PostgreSQL).

API iniziali:

- `GET /api/health`
- `GET /api/works` (catalogo completo con disponibilità di TEI e metadati)
- `GET /api/works/acarnesi`
- `GET /api/works/acarnesi/speeches`
- `GET /api/terms?work=acarnesi&limit=30`
