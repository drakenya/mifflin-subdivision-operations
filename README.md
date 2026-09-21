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

## Web UI (editing data)

Prefer forms to hand-editing YAML? Start the local UI:

```bash
uv run waybill serve            # http://127.0.0.1:8000  (add --open to launch a browser)
```

Every reference field (commodity, shipper, consignee, locations, …) is a type-to-search dropdown,
and industries that ship or receive the chosen commodity are listed first. Edits are staged in
memory — the header shows how many are unsaved. **Review & Save** shows a diff of exactly what will
change in each YAML file (nothing else is touched, including your comments) and writes it when you
say so; **Discard** throws staged edits away. If a file changed on disk while you were editing, you
are asked whether to reload it or overwrite it.

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
  for layout in ak_main experimental_1; do
    uv run waybill --layout "$layout" generate --session "$session" --output "output/compare-$name-$layout.pdf"
  done
done
```

## Card Types

The `modeling_the_sp` layout matches each waybill type's fonts, spacing,
and field layout against a specific prototype scan wherever one could be
found. Sources are from Tony Thompson's *Modeling the SP* blog
(modelingthesp.blogspot.com) unless noted. Fonts used across the layout
(Mom's Typewriter Actual for values, Franklin Gothic Medium for labels)
were likewise sourced from that blog's account of Thompson's own process,
cross-referenced against his personal font library.

### LOADED — Freight Waybill

Standard AAR Form 98 freight waybill; this is the primary reference the
whole `modeling_the_sp` layout (car card + waybill body) was matched
against.

- [Diamond Alkali chlorine waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgwoWdHbhDvP4Q3_X896X3THqUNQi9Ckn940sPvPrvYFiRFmrw5At8GYoKs3473yEIV9NX9neZv0TP1uNiAqKzJT-zu7Vw6504FXMp6YO005VF3W7bkoN4qQYeKMjXZxAe2lNn21y1tZEKEmufwQBDr77G-woLY3fndycSgJ2rXx0EDI8dKdsfRR6N6QLM/s720/DX%20WB.jpg) —
  _Source_: [Waybills, Part 131: Model Bill Production](https://modelingthesp.blogspot.com/2026/06/waybills-part-131-model-bill-production.html)

### EMPTY — Empty Car Bill

SP Form 151, with "FOR HOME" / "FOR LOADING" sections.

- [Home bill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgUTdgo9q69VcmIJgYgSJymcQwiBCS4_GfRIFZxwZUbI1Es0fu_L7t_FH64Z7JVtdfJFcF_Vgqgj6lcEmRFfLCMtlbYX_BOC8EzR_vbsQ51j7RG9YwGaCEZp_PugFsboQEg8tmbnhQkpSE/s1600/home-bill.gif),
  [loading bill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhZhsOqxD3xCUmKD1ypMy3kX9BV804SDFpHVfVfEcgq-nzMEC5UJ2RsaEUjfSVWYNHIeuXiHDmdcm_TxUi-Wv4jMP5G1sUE1R3XOqeY-Wa8542KGV6J4ypiiqylQgTcjE5RQEgc3EE5jIs/s1600/load-bill.gif) —
  _Source_: [Waybills, Part 8](https://modelingthesp.blogspot.com/2011/06/waybills-8.html)

### DEADHEAD — Deadhead Order

No prototype reference turned up in the blog archive; this layout is an
original design, not matched against a specific form.

### MOW — M-O-W Service

No distinct form exists — Thompson fills out M-O-W moves on the same
standard Freight Waybill used for revenue loads, so both layouts route
MOW waybills through the LOADED renderer via a field-mapping adapter
(see `_draw_mow` in `ak_main.py` / `modeling_the_sp.py`).

- [SP 13584, ballast to an outfit track](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgHVUw96YuEujE-TDareyEGBKff3qyYHjBtV8t2aipCfOhzZLKBeKrjx1sUmLyFUVfojOIGFqUmzb3l4AcQb2MwP0j3Ub9oQOoSYGxfGybxXmE0W0ZWTF6DeMyjRpLzPTZ8I6e_2yFduqg/s1600/SP+13584+ld.jpg) —
  _Source_: [Waybills, Part 43: Operations With MOW Cars](https://modelingthesp.blogspot.com/2015/08/waybills-part-43-operations-with-mow.html)

### HOLD — Hold Order

No prototype reference turned up in the blog archive; original design.

### BAD_ORDER — Bad Order Card

SP Form L-7017-A, with its distinctive diagonal red stripe.

- [SP Bad Order card](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhaI1iunQwEXqJpRWZWXezt_qLi28FeJRBbr7jPXGcCaJOG2lMc6OmTake5C-QkBrRKa8eezAWQgdQzmE3-nnxX40u5hUGR5IXyqn_Dn8oHKkAzgAuN1XSqFy8UaG5SKix4Ga3_MjZ0SYw/s1600/bad+order+SP.jpg) —
  _Source_: [A New Bad-Order Card](https://modelingthesp.blogspot.com/2018/04/a-new-bad-order-card.html)

### STOP_OFF — Stop Off

AAR Form AD-142 — not a full waybill, but an overlay card that rides
atop the regular waybill in the sleeve, flagging a car that must stop
en route to partially unload or complete loading.

- [Stop Off card paired with its matching Freight Waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEioAVXLAQ_QMj3cKKQbLjbAk8j_QBMraBLug9E9s6iP65dtrAW62IL1qTvhDOpeqeE6RqDdGtP-jTNe7b2_-7cMmSxRp0_Q32Xqxjpq-P1na-3eGBbFunimx2cg8_mShEDooC6CgdAa3zc/s1600/model+slip.jpg) —
  _Source_: [Waybills, Part 47: the Stop-Off Form](https://modelingthesp.blogspot.com/2016/01/waybills-part-47-stop-off-form.html)

### TEMPORARY — Conductor's Memorandum Waybill

SP Form 704, Part 2 — used when a car must move before its regular
waybill is ready (e.g. a non-agency-station pickup).

- [Form 704, Part 2, filled out (prunes, Ballard → Portland)](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhJJX2iPCjosDnW-vJlsZu6xSbJAlM9Tv6CbU5i0-9wV4savWB0JxO2VECbnDOcIl5TyYMWYZPz_IxAOC98-kRxwoIjM-SOQDLj9OdUzMi3sLc71VBnjZajLc_MhKHkhV_o9GBkE6qU4xk/s840/704+filled.jpg) —
  _Source_: [Waybills, Part 91: Model Form 704](https://modelingthesp.blogspot.com/2021/09/waybills-part-91-model-form-704.html)
  (background on the prototype form: [Part 90: the SP Form 704](https://modelingthesp.blogspot.com/2021/09/waybills-part-90-sp-form-704.html))

### PERISHABLE — Perishable Freight Waybill

Pink-stock AAR perishable waybill, simplified from the full original
the same way Thompson simplified his own model version.

- [Filled example — PFE reefer, cantaloupes, Firebaugh → Willimantic](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjSfe5uBVD5NLwaRozTpMXVh5Q6Ml2_jcGLPMZJV0bzR7zEJeiBBBJxTWH6UmKMPzR9urXsrSt-R1c-eOUy63c6bFre89rcqkdXqBNsyYl6xIWcHOEYYQZ1IB2AG9-zKyHUoCwJD5ua6Po/s1600/perish+bill.jpg) —
  _Source_: [Waybills, Part 70: Other Waybill Forms](https://modelingthesp.blogspot.com/2020/06/waybills-part-70-other-waybill-forms.html)

### LIVESTOCK — Live Stock Freight Waybill

Shares the Perishable form's skeleton, swapping commodity for head
count/description and icing fields for loading/bedding/feeding
yes-or-no questions.

- [Filled example — 36 head of steers, Northfield → N. Platte](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEinItJwVBLRsZWzyH_TuhbDHwSXhB6J4xFjZ3iiur_Lm2q9AqsvuLbngfBgm1UKXvJoBs3bIm7EGN5EnUq2gfagv3nAd7_xHCp4ExqCqswVbJQWnleTM9kYRmGNJSzh0gthhfBNp7TspZY/s1600/SP+73079.jpg) —
  _Source_: [Waybills, Part 70: Other Waybill Forms](https://modelingthesp.blogspot.com/2020/06/waybills-part-70-other-waybill-forms.html)

# References

## Modelling the SP

- [Current Waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEj2v9XKTfo7GVLdy8TJno29u-3Vz7usZklCsokqliOsuWccLnQwsMswoW2jGWSotsjzaO9wOqXCt7xCxltrRXUzW1XIoTDFg5f7Su4_JWzS0Fu7OC1tk7UtX1dXnN5Rss0uRA5KjDocc1h_bDIzMouJcBj_TKqLsxcytIJ49ElKuuqXjXH1GMqim-o1cIc/s600/SP%20example.jpg) (_Source_: [Waybills, Part 131: Model Bill Production](https://modelingthesp.blogspot.com/2026/06/waybills-part-131-model-bill-production.html))

- [Waybill](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiVVnVkvat0nRT-khQaC9LS1FbUfQ9mmxKKYTk6w7winN5X7Kn8G32wd54531eJkffAZKj-u_buT1BUm-9UveU2YU-UdJLEZWAvLTd-eQloY3Ur6O3XLtROicYxip5BAnGS9Lp3TYaQu8E/s1600/oil+bills.jpg)
- [Empty Car](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiVVnVkvat0nRT-khQaC9LS1FbUfQ9mmxKKYTk6w7winN5X7Kn8G32wd54531eJkffAZKj-u_buT1BUm-9UveU2YU-UdJLEZWAvLTd-eQloY3Ur6O3XLtROicYxip5BAnGS9Lp3TYaQu8E/s1600/oil+bills.jpg)