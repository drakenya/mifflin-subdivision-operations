# Waybill Generator

Generates printable car card + waybill PDFs for PRR model railroad operations.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
uv run waybill --help
```

## Data Files

Edit files in `data/` to define your roster:

- `data/cars.yaml` — your car fleet
- `data/locations.yaml` — layout locations and industries
- `data/commodities.yaml` — freight types
- `data/waybills.yaml` — waybill definitions

## Printing Cards

1. Create a session file listing which car gets which waybill:

```yaml
# session.yaml
cards:
  - car: PRR-12345
    waybill: waybill-1
  - car: PRR-67890
    waybill: empty-1
```

2. Generate the PDF:

```bash
uv run waybill generate --session session.yaml
```

Output lands in `./output/waybills-YYYY-MM-DD.pdf`. Print portrait,
cut on crop marks. Each page holds 9 cards (3×3).

## Validation

```bash
uv run waybill validate
```

Reports any schema errors in your data files before you try to print.

## Industry Database Browser

`tools/industry-browser.html` is a standalone page for searching and
filtering the ~73k industry records converted from the OpSIG/JBritton
source files (`uv run waybill convert-industry-db`). It reads directly
from the generated `industry_database/` JSON, so serve the repo over
HTTP rather than opening the file directly:

```bash
uv run waybill convert-industry-db   # if industry_database/ doesn't exist yet
uv run python -m http.server 8000    # from the repo root
```

Then open `http://localhost:8000/tools/industry-browser.html`.

## Development

```bash
uv run pytest              # run tests
uv run ruff check .        # lint
```

Adding a dependency:

```bash
uv add <package>            # runtime dependency
uv add --dev <package>      # dev-only dependency
```

### Regenerate test output PDFs

```bash
for session in sessions/test-*.yaml; do
  uv run waybill --layout experimental_1 generate --session "$session" --output "output/$(basename "$session" .yaml).pdf"
done
```

```bash
for session in sessions/test-*.yaml; do
  uv run waybill generate --session "$session" --output "output/$(basename "$session" .yaml).pdf"
done
```

### Compare layouts side by side

Generate every session through every layout to compare them directly:

```bash
for session in sessions/test-*.yaml; do
  name=$(basename "$session" .yaml)
  for layout in modelling_the_sp experimental_1; do
    uv run waybill --layout "$layout" generate --session "$session" --output "output/compare-$name-$layout.pdf"
  done
done
```

# References

## Modelling the SP

- [Current Waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEj2v9XKTfo7GVLdy8TJno29u-3Vz7usZklCsokqliOsuWccLnQwsMswoW2jGWSotsjzaO9wOqXCt7xCxltrRXUzW1XIoTDFg5f7Su4_JWzS0Fu7OC1tk7UtX1dXnN5Rss0uRA5KjDocc1h_bDIzMouJcBj_TKqLsxcytIJ49ElKuuqXjXH1GMqim-o1cIc/s600/SP%20example.jpg) (_Source_: [Waybills, Part 131: Model Bill Production](https://modelingthesp.blogspot.com/2026/06/waybills-part-131-model-bill-production.html))

- [Waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiVVnVkvat0nRT-khQaC9LS1FbUfQ9mmxKKYTk6w7winN5X7Kn8G32wd54531eJkffAZKj-u_buT1BUm-9UveU2YU-UdJLEZWAvLTd-eQloY3Ur6O3XLtROicYxip5BAnGS9Lp3TYaQu8E/s1600/oil+bills.jpg)
- [Empty Car](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiVVnVkvat0nRT-khQaC9LS1FbUfQ9mmxKKYTk6w7winN5X7Kn8G32wd54531eJkffAZKj-u_buT1BUm-9UveU2YU-UdJLEZWAvLTd-eQloY3Ur6O3XLtROicYxip5BAnGS9Lp3TYaQu8E/s1600/oil+bills.jpg)