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
