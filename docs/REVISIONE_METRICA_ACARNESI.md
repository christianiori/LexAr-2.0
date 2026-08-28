# Revisione metrica degli *Acarnesi*, vv. 1–46

## Stato del pilot

Il sidecar `tools/data/ach-metrics.json` contiene 46 proposte, corrispondenti ai
vv. 1–46 e a 51 frammenti TEI. Nessuna proposta è ancora marcata come
`verified`: la validazione automatica garantisce copertura, riferimenti,
notazione e stabilità strutturale, ma non sostituisce una revisione filologica.

| Stato | Versi |
| --- | ---: |
| Proposti, certezza media | 40 |
| Proposti, certezza bassa | 6 |
| Verificati | 0 |
| Senza realizzazione `real` | 3 |

## Casi a bassa certezza

| Verso | Testo | Questione da verificare | Decisione corrente |
| ---: | --- | --- | --- |
| 15 | Τῆτες δ’ ἀπέθανον καὶ διεστράφην ἰδών | Trattamento di δ’ ἀπέθανον e διεστράφην | Conservata la proposta automatica con certezza bassa. |
| 18 | οὕτως ἐδήχθην ὑπὸ κονίας τὰς ὀφρῦς | Quantità di κονίας e correptio finale | Conservata la proposta automatica con certezza bassa. |
| 20 | ἑωθινῆς ἔρημος ἡ πνὺξ αὑτηί | Sequenza finale e quantità del deittico αὑτηί | `real` omesso: nessuna scansione viene presentata come risolta. |
| 37 | Νῦν οὖν ἀτεχνῶς ἥκω παρεσκευασμένος | Sequenza centrale e possibile sinizesi in παρεσκευασμένος | `real` omesso: il verso resta esplicitamente aperto. |
| 40 | Ἀλλ’ οἱ πρυτάνεις γὰρ οὑτοιὶ μεσημβρινοί | Quantità di οὑτοιί e del segmento finale di μεσημβρινοί | Conservata la proposta automatica con certezza bassa. |
| 43 | Πάριτ’ εἰς τὸ πρόσθεν | Prosa oppure monometro giambico ipercatalettico secondo Starkie | Registrata l’ipotesi alternativa `ia1-hypercat`, senza `real`. |

I vv. 20, 37 e 43 sono quindi documentati ma non risolti. Nel lettore sono
segnalati come «da verificare» e mostrano soltanto lo schema di riferimento.

## Protocollo di revisione manuale

Per ogni verso il revisore deve:

1. confrontare testo, eventuali interventi editoriali e nota metrica con la
   fonte dichiarata;
2. controllare quantità, risoluzioni, correptio, sinizesi, cesure e divisioni
   fra battute;
3. aggiornare `real`, `cert` e la nota nel sidecar senza modificare il testo
   greco;
4. impostare `status` a `verified` soltanto con `cert: high`, una realizzazione
   completa e un oggetto `review` con revisore, data ISO e nota sulla fonte;
5. eseguire `python tools/apply_ach_metrics.py`, quindi
   `python tools/check_project.py`.

Esempio minimo del dato richiesto per una scansione verificata:

```json
"status": "verified",
"cert": "high",
"review": {
  "reviewer": "Nome del revisore",
  "date": "2026-08-28",
  "source_note": "Riscontro autoptico su Starkie 1909, nota al verso."
}
```

## Fonti dichiarate

- W. J. M. Starkie (ed.), *The Acharnians of Aristophanes*, London,
  Macmillan, 1909.
- Diorisis Scan 0.2, impiegato esclusivamente per generare proposte non
  autoritative.

Le coordinate del testo e le responsabilità complete restano registrate nel
TEI `xml/ach.xml` e nel sidecar metrico.
