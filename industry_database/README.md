# Industry Database

Source files for bulk import into `data/industry_catalog.yaml` via `waybill import`.

## Directory layout

```
industry_database/
  opsig/              OpSIG files (.txt and .xls)
  jbritton/           JBritton files (.txt)
  commodity_map.yaml  User-maintained commodity normalization overrides
  opsig_car_map.yaml  Pre-populated OpSIG car code → AAR code map
```

## OpSIG .txt format

10-column TSV, Windows CRLF (latin-1 encoding):

| Col | Field      | Notes                             |
|-----|------------|-----------------------------------|
| 0   | year       | e.g. `2004`, `55`, `90`           |
| 1   | name       | Industry name                     |
| 2   | city       |                                   |
| 3   | state      | 2-letter abbreviation             |
| 4   | railroad   | e.g. `PRR`, `P&W`, `CSX`         |
| 5   | direction  | `S` (ships) or `R` (receives)     |
| 6   | commodity  | Free-text                         |
| 7   | notes      | Description / process notes       |
| 8   | volume     | e.g. `VH`, `H(e)`, `M-H`         |
| 9   | car_types  | Comma-sep OpSIG codes, e.g. `CH,T`|

## OpSIG .xls format

Assumed same column layout as .txt. Verify during import — if columns differ,
update this README and `opsig.py`.

## JBritton .txt format

256-column wide TSV, Windows CRLF (latin-1 encoding). Most columns are empty.
Effective columns:

| Col | Field        | Notes                                   |
|-----|--------------|-----------------------------------------|
| 0   | year         |                                         |
| 1   | name         | Industry name                           |
| 2   | city         |                                         |
| 3   | state        |                                         |
| 4   | railroad     |                                         |
| 5   | direction    | `S`, `R`, or blank (station/delivery)   |
| 6   | commodity    | Free-text, or blank                     |
| 7   | (blank)      |                                         |
| 8   | location_ref | Division + milepost (stored as `notes`) |
| 9   | source_ref   | e.g. `pennsyrr.com PRR CT1000`          |

No car types. Car types are inferred from matched commodity ids.

## commodity_map.yaml

User-editable. Case-insensitive exact match on `source_text`.
`commodity_id: null` suppresses the entry from the unmatched-commodities report.

## opsig_car_map.yaml

Pre-populated. Do not edit casually — maps OpSIG shorthand to AAR codes.
Add new mappings when unknown codes appear in import reports.
