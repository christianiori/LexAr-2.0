# Pagine e rotte pubbliche

Questo documento definisce gli URL canonici di LexAr. I collegamenti interni
devono usare questi percorsi e non creare alias o copie delle pagine.

## Pagine principali

| Sezione | URL canonico |
| --- | --- |
| Home | `/` oppure `/index.html` |
| Il progetto | `/infogen/intro.html` |
| Catalogo delle opere | `/catalogo/catalogo1.html` |
| Lessico generale | `/lessico/lessicogen.html` |

Ogni pagina HTML deve contenere un collegamento a Home, Catalogo e Lessico
generale. `tools/check_internal_links.py` verifica automaticamente questa
regola.

## Pagine informative

| Pagina | URL canonico |
| --- | --- |
| Autore | `/infogen/autore.html` |
| Linea del tempo | `/infogen/timeline.html` |
| Glossario | `/infogen/glossario.html` |

## Strumenti lessicali

| Strumento | URL canonico |
| --- | --- |
| Tutti i vocaboli | `/lessico/vocaboli.html` |
| Campi semantici | `/lessico/lesamb.html` |
| Radici | `/lessico/radici.html` |

## Opere

| Opera | URL canonico |
| --- | --- |
| Acarnesi | `/item/acarnesi.html` |
| Cavalieri | `/item/cavalieri.html` |
| Nuvole | `/item/nuvole.html` |
| Vespe | `/item/vespe.html` |
| Pace | `/item/pace.html` |
| Uccelli | `/item/uccelli.html` |
| Donne alle Tesmoforie | `/item/tesmoforie.html` |
| Lisistrata | `/item/lisistrata.html` |
| Rane | `/item/rane.html` |
| Donne al Parlamento | `/item/donne.html` |
| Pluto | `/item/pluto.html` |

## API

| Funzione | Rotta |
| --- | --- |
| Stato del servizio | `GET /api/health` |
| Elenco delle opere | `GET /api/works` |
| Dati di un'opera | `GET /api/works/{slug}` |
| Battute di un'opera | `GET /api/works/{slug}/speeches` |
| Termini frequenti | `GET /api/terms?work={slug}&limit={1-100}` |

Attualmente `acarnesi` è l'unico slug con un testo TEI completo. Le rotte delle
altre opere restituiscono i metadati disponibili senza simulare un testo non
ancora presente.

## File editoriali pubblici

- `/xml/ach.xml`: testo TEI degli *Acarnesi*;
- `/xml/metach.xml`: metadati degli *Acarnesi*;
- `/xml/mettesm.xml`: metadati delle *Donne alle Tesmoforie*.

Il database `data/lexar.sqlite3` è generato localmente, escluso da Git e bloccato
dal server HTTP. `script/data/work-texts.js` è invece il solo output generato
conservato nel repository, perché permette al lettore degli *Acarnesi* di
funzionare senza backend.

## Inventario delle risorse

L'audit iniziale della Fase 1 ha confermato che:

- tutte le 21 pagine HTML sono raggiungibili tramite collegamenti interni;
- tutti i fogli di stile e gli script presenti sono ancora utilizzati;
- il vecchio layout condiviso in `style/style.css` e `script/script.js` resta
  necessario finché non saranno completate le Fasi 3–6;
- `lessico/RADICIDEF.json` e `lessico/radici_completo.json` sono dati lessicali
  da ricondurre a una fonte unica durante la Fase 6, non output del backend;
- il precedente archivio `lessico/RADICIDEF.zip`, copia compressa e non usata di
  `RADICIDEF.json`, è stato rimosso perché ridondante;
- i pulsanti verso file XML/TEI non presenti sono disabilitati e dichiarano
  esplicitamente che la risorsa non è disponibile.

Il controllo non verifica la disponibilità dei siti esterni: controlla file,
ancore e risorse locali, compresa la corretta distinzione tra maiuscole e
minuscole nei percorsi.
