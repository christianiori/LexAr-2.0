# LexAr

Sito dedicato al lessico nelle commedie aristofanee.

## Avvio locale con API

Il progetto include un backend locale senza dipendenze esterne. All'avvio importa
il TEI degli *Acarnesi* in un database SQLite generato in `data/lexar.sqlite3`.

```powershell
python server.py
```

Apri quindi `http://localhost:8000/` nel browser.

API iniziali:

- `GET /api/health`
- `GET /api/works`
- `GET /api/works/acarnesi`
- `GET /api/works/acarnesi/speeches`
- `GET /api/terms?work=acarnesi&limit=30`
