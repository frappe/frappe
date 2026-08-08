# Typst PDF renderer — lifecycle

How a builder (beta) print format renders through Typst, call by call. Typst is
an opt-in `pdf_generator` for builder formats; Chromium stays the default. The
`typst` package (a self-contained wheel, no system dependencies) is a regular
frappe dependency, so every bench — self-hosted, Docker, Frappe Cloud — has it
after installing requirements.

## From "Download PDF" to the response

| # | What happens | Where |
|---|---|---|
| 1 | Browser calls the whitelisted endpoint | `print_format_generator.download_pdf` |
| 2 | Print permission checked, format resolved; non-builder formats hand off to the legacy Jinja pipeline | `download_pdf()` → `validate_print()`, `resolve_print_format()` |
| 3 | `format_data` JSON parsed into a layout, then resolved: permlevel-restricted fields stripped, `visible_if` conditions applied, table columns pruned, letter head picked. **Both renderers read this one resolved layout, so they can never disagree on what a user may see** | `PrintFormatGenerator.__init__`, `apply_permlevel_access()`, `get_letterhead()` |
| 4 | Dispatch on the format's `pdf_generator`: `"chrome"` → existing HTML + Chromium path, untouched; `"Typst"` → continue. This is the only Typst dispatch point | `render_pdf()` |
| 5 | **Gate re-check**: `typst_blockers()` (same gate that ran at save) plus `letterhead_blockers()` on the letter head that will actually print. Any blocker → a loud error naming each one. Never a silent fallback | `typst_emitter.typst_blockers()`, `letterhead_blockers()` |
| 6 | Google Font TTFs ensured in the per-site cache (`sites/<site>/typst_fonts`); fetched once, failures negative-cached so offline sites don't stall | `ensure_typst_fonts()` |
| 7 | The emitter walks the resolved layout and renders header, body, footer to Typst source; images and image letter heads register as embedded assets | `TypstEmitter.prepare()`, `emit()` |
| 8 | Optional measure pass (only when Print Settings repeat header/footer on every page): a tiny `measure.typ` is compiled and `typst.query()` returns the real header/footer heights so page margins reserve room | `measure_source()`, `typst.query()` |
| 9 | `main.typ` + assets written to a fresh temp dir; `typst.compile()` — a Rust library inside the Python worker, no subprocess — returns the PDF bytes. The temp dir is also the compile sandbox: file reads outside it are refused | `render_typst_pdf()`, `typst.compile()` |
| 10 | Bytes into `frappe.local.response`. Email attachments take the same path via `attach_print` | |

## The gate

`typst_blockers()` is the single authority on what may render through Typst,
enforced at three places: the builder UI (mirrored client-side in
`print_format_builder/utils.js` to grey the option live), save
(`validate_typst_renderer`), and render (step 5). A format either renders
fully through Typst or is refused with every reason named. Blockers: custom
HTML formats, custom CSS, HTML blocks, Jinja field templates, non-QR barcodes,
remote image URLs, HTML letter heads, and CSS `custom_style` properties or
values the translator cannot express.

## How JSON becomes Typst

A two-field format:

```json
{ "sections": [{ "columns": [{ "fields": [
	{ "fieldtype": "Data", "fieldname": "description", "label": "Task" },
	{ "fieldtype": "Data", "fieldname": "status", "label": "Status",
	  "value_color": "#1D9E75" }
] }] }] }
```

emits (with `doc.description = 'Review "Typst" PR #41690'`):

```typst
#set page(width: 210mm, height: 297mm, margin: (top: 15.0mm, bottom: 15.0mm, left: 15.0mm, right: 15.0mm))
#set text(size: 10.5pt)
#block(width: 100%)[
#stack(spacing: 8pt,
[#stack(spacing: 4pt,
[#text(size: 0.85em, fill: rgb("#6b7280"), "Task")],
[#text("Review \"Typst\" PR #41690")])],
[#stack(spacing: 4pt,
[#text(size: 0.85em, fill: rgb("#6b7280"), "Status")],
[#text(fill: rgb("#1D9E75"), "Open")])])
]
#v(6.0pt)
```

Three things to notice:

- Every document value crosses through `q()` — a JSON-quoted string literal
  with `ensure_ascii=False`. The `"` is escaped, the `#` is inert inside a
  string: content can never become Typst code, and non-ASCII text (₹, é, 日本語)
  prints as-is.
- Colors from `format_data` only reach the output through `safe_color()`
  (strict hex pattern); everything else is dropped or blocks.
- Structure maps directly: a column of fields → `#stack`, columns side by side
  → `#grid`, builder px → pt at 0.75 (matching CSS).

## Fieldtype dispatch

| Node | Emitter | Output |
|---|---|---|
| Data, Currency, Date, … | `_data_field()` | label + `#text(q(value))` |
| Table | `_table()` / `_table_cell()` | `#table` incl. merged cells, image thumbnails |
| Repeater | `_repeater()` | `#table` from per-row template tokens |
| Image / Attach Image | `_image()` → `_embed_image()` | `#image` on an embedded asset |
| Barcode (QR) | `_barcode()` | `#image` of the server-rendered SVG |
| Spacer / Divider | inline | `#v(…)` / ruled `#block` |
| HTML, Field Template, non-QR barcode | — | blocked; format stays on Chromium |

## Measured

Request for Quotation, same document and format, 10 warm renders after a
warm-up; memory is peak RSS of processes spawned for the render.

| | Chromium | Typst |
|---|---:|---:|
| A typical print | 808 ms | 109 ms |
| The slowest print out of 10 | 892 ms | 112 ms |
| The very first print after a restart | 1325 ms | 672 ms |
| Extra RAM used while printing | 257 MB | 39 MB |
| Size of the PDF (same document) | 78 KB | 21 KB |
| Bulk print, 10 documents (multi-PDF) | 8.0 s | 0.9 s |
