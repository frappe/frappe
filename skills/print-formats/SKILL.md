---
name: print-formats
description: Create or change a Frappe print format, either as a Print Format Editor layout (format_data JSON) or as a custom Jinja HTML format, and check it by rendering a PDF. Use for any print format, letter head or PDF layout work on a site or in an app.
---

# Creating print formats

A print format is a `Print Format` document linked to a DocType. There are two kinds:

| Kind | Fields that matter | When to use it |
| --- | --- | --- |
| Editor format | `print_format_builder_beta = 1`, `format_data` (layout JSON) | The default. Fields, tables, text, images, barcodes and HTML blocks placed in sections and columns. Users can keep editing it in the Print Format Editor. |
| Custom Jinja format | `custom_format = 1`, `print_format_type = "Jinja"`, `html` | Only when the layout cannot be built from editor blocks. Nobody can edit it in the editor. |

Prefer an editor format. When one part needs custom markup, put an HTML block in an editor format instead of writing the whole format in Jinja.

Read [LAYOUT.md](LAYOUT.md) for every key of the layout JSON before you write one.

Take every `fieldname`, `fieldtype`, `label` and child table `options` from `frappe.get_meta(doctype)`, including fields you read in Jinja. A wrong name in `global_variables` stops the whole print with an error.

## Create an editor format

```python
import frappe

pf = frappe.get_doc({
	"doctype": "Print Format",
	"name": "Example Invoice",
	"doc_type": "Sales Invoice",
	"print_format_builder_beta": 1,
	"pdf_generator": "PlutoPrint",
	"margin_top": 15, "margin_bottom": 15, "margin_left": 15, "margin_right": 15,
	"font": "Inter",
	"font_size": 14,
	"page_number": "Bottom Center",
	"format_data": frappe.as_json(layout),
})
pf.insert()
```

- `before_save` sets `print_format_builder_beta = 1` on any new format that is not custom, standard or a Print Designer format, but set it anyway.
- Only `name` and `doc_type` are needed. `module` is filled from the DocType when left out. Everything else in the example is optional.
- Margins are in mm. `font` is a Google Fonts family name; empty or `Default` prints Inter. `font_size` is in px, default 14.
- `page_number` is one of `Hide`, `Top Left`, `Top Center`, `Top Right`, `Bottom Left`, `Bottom Center`, `Bottom Right`. Default `Hide`.
- Write `format_data` only. `draft_data` holds unsaved editor edits and must stay empty.
- In an app, export the format as a standard format (`standard = "Yes"`, developer mode) so its JSON lands in `<app>/<module>/print_format/<name>/`.

## PDF renderer

`pdf_generator` picks the engine. The choices come from `frappe.utils.print_utils.get_pdf_generators()`.

| Value | Use it for |
| --- | --- |
| `PlutoPrint` | The default. Fast, no browser process. |
| `chrome` | Formats that need scripts, CSS grid or a page range. Validation falls back to it when PlutoPrint cannot print a format. |
| `Typst` | Editor formats only, without HTML blocks. Allows Typst blocks. See [frappe/printing/typst_renderer.md](../../frappe/printing/typst_renderer.md). |

A Typst block only prints with `Typst`, and saving fails otherwise. `validate_typst_renderer` names what blocks Typst.

## Letter heads

The letter head comes from, in order: the `letterhead` argument when printing, the layout's `letter_head` key (an empty string removes it), the document's `letter_head` field, then the default `Letter Head`. Print Settings `with_letterhead` turns letter heads off when no argument is passed. Put company details that repeat on every format in a Letter Head, not in each format.

## Custom Jinja formats

```python
frappe.get_doc({
	"doctype": "Print Format",
	"name": "Example Delivery Slip",
	"doc_type": "Delivery Note",
	"custom_format": 1,
	"print_format_type": "Jinja",
	"html": "<h2>{{ doc.name }}</h2>{% for row in doc.items %}<p>{{ row.item_name }}</p>{% endfor %}",
}).insert()
```

The template gets `doc`. Use `doc.get_formatted("fieldname")` for values so currency, dates and numbers follow the user's settings. `validate_template` checks the Jinja on save.

## Check your work

Always render the format and look at the result. Never hand over a format you did not render.

```python
html = frappe.get_print("Sales Invoice", name, print_format="Example Invoice")
pdf = frappe.get_print("Sales Invoice", name, print_format="Example Invoice", as_pdf=True)
open("/tmp/example.pdf", "wb").write(pdf)
```

Then check:

- The PDF opens and has the pages you expect (`pdftotext`, `pdfinfo`, or `pypdf`).
- Every field shows a value. Fields that are empty on the record, and table columns that are empty in every row, are left out on purpose.
- A submittable document in draft prints a DRAFT heading when Print Settings `add_draft_heading` is on. Test with a submitted record for the final look.
- Render once with each renderer the format may use, when you change shared styles.
