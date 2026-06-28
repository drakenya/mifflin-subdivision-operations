# Waybill Generator

Generates printable car card + waybill PDFs for PRR model railroad operations.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
waybill --help
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
waybill generate --session session.yaml
```

Output lands in `./output/waybills-YYYY-MM-DD.pdf`. Print portrait,
cut on crop marks. Each page holds 9 cards (3×3).

## Validation

```bash
waybill validate
```

Reports any schema errors in your data files before you try to print.

## Development

```bash
pytest              # run tests
ruff check .        # lint
```

### Regenerate test output PDFs

```bash
for session in sessions/test-*.yaml; do
  waybill --layout experimental_1 generate --session "$session" --output "output/$(basename "$session" .yaml).pdf"
done
```

```bash
for session in sessions/test-*.yaml; do
  waybill generate --session "$session" --output "output/$(basename "$session" .yaml).pdf"
done
```

# References

## Modelling the SP

- [Current Waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEj2v9XKTfo7GVLdy8TJno29u-3Vz7usZklCsokqliOsuWccLnQwsMswoW2jGWSotsjzaO9wOqXCt7xCxltrRXUzW1XIoTDFg5f7Su4_JWzS0Fu7OC1tk7UtX1dXnN5Rss0uRA5KjDocc1h_bDIzMouJcBj_TKqLsxcytIJ49ElKuuqXjXH1GMqim-o1cIc/s600/SP%20example.jpg) (_Source_: [Waybills, Part 131: Model Bill Production](https://modelingthesp.blogspot.com/2026/06/waybills-part-131-model-bill-production.html))

- [Waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiVVnVkvat0nRT-khQaC9LS1FbUfQ9mmxKKYTk6w7winN5X7Kn8G32wd54531eJkffAZKj-u_buT1BUm-9UveU2YU-UdJLEZWAvLTd-eQloY3Ur6O3XLtROicYxip5BAnGS9Lp3TYaQu8E/s1600/oil+bills.jpg)
- [Empty Car](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiVVnVkvat0nRT-khQaC9LS1FbUfQ9mmxKKYTk6w7winN5X7Kn8G32wd54531eJkffAZKj-u_buT1BUm-9UveU2YU-UdJLEZWAvLTd-eQloY3Ur6O3XLtROicYxip5BAnGS9Lp3TYaQu8E/s1600/oil+bills.jpg)