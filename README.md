# LexAr

Sito dedicato al lessico nelle commedie aristofanee.

## Avvio locale con API

Il progetto include un backend locale senza dipendenze esterne. All'avvio importa
il TEI degli *Acarnesi* in un database SQLite generato in `data/lexar.sqlite3`.

```powershell
python server.py
```

Apri quindi `http://localhost:8000/` nel browser.

## Deploy su Render

La configurazione in `render.yaml` crea un Web Service Python e usa
`/api/health` come controllo di integrità. Render assegna la variabile `PORT`,
che il server legge automaticamente. Il database SQLite viene ricreato dal TEI
ad ogni avvio: finché LexAr resta in sola lettura non richiede un disco
persistente. Prima di aggiungere utenti o annotazioni condivise, sarà necessario
un database persistente (PostgreSQL).

API iniziali:

- `GET /api/health`
- `GET /api/works`
- `GET /api/works/acarnesi`
- `GET /api/works/acarnesi/speeches`
- `GET /api/terms?work=acarnesi&limit=30`
