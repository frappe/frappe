# Print Format Editor layout

`format_data` is a JSON object. `frappe/utils/print_format_generator.py` reads it, `frappe/templates/print_format/print_format.html` and `macros/*.html` print it. Keys that are not listed here are ignored or dropped.

```json
{
	"header": {"columns": [{"fields": [...]}]},
	"sections": [
		{"label": "", "columns": [{"label": "", "width": 50, "fields": [...]}, {"width": 50, "fields": [...]}]}
	],
	"footer": {"columns": [{"fields": [...]}]},
	"page": {"size": "A4", "orientation": "Portrait"},
	"letter_head": "Example Letter Head",
	"global_variables": "{% set customer_group = frappe.db.get_value('Customer', doc.customer, 'customer_group') %}"
}
```

## Top level

| Key | Value |
| --- | --- |
| `header`, `footer` | A zone: `{"columns": [...]}`. Printed at the top and bottom of every page. Takes the same columns (with `width`) and fields as a section. |
| `sections` | List of sections, printed in order. |
| `page` | `size`: a Print Settings `pdf_page_size` value such as `A4`, `A5`, `Letter`, `Legal`. `orientation`: `Portrait` or `Landscape`. Leave it out to use Print Settings. |
| `letter_head` | Name of a Letter Head. An empty string prints none. Leave the key out to follow the document. |
| `global_variables` | Jinja with top level `{% set name = ... %}` statements. Rendered once per print with `doc` and the usual print Jinja globals such as `frappe`, and every name it sets is available in every HTML block. Guard against empty values: `{% set greeting = 'Dear ' ~ (doc.customer_name or '') %}`. Do slow lookups here, not in each block. |
| `background` | `{"image": "/files/example.png", "opacity": 30}`. A page background image. |

## Sections

| Key | Value |
| --- | --- |
| `label`, `show_label` | Section heading. `show_label: "hide"` keeps the label for the editor but does not print it. A section with a label and no values is skipped. |
| `columns` | List of columns. `width` is a relative weight (flex grow), so `[50, 50]` and `[1, 1]` are the same. To push a block to the right, put an empty column before it, as the totals in the full example do. |
| `gap` | Space between columns in px. Default 20. |
| `justify` | `space-between`, `space-evenly`, `center` or `right-end`. |
| `field_orientation` | `left-right` prints each label beside its value. Default is label above value. |
| `margin`, `padding` | `{"top": 0, "right": 0, "bottom": 0, "left": 0}` in px. |
| `background`, `radius` | A CSS colour, and a corner radius in px. |
| `field_borders` | `1` prints the section as a grid of bordered cells. With it: `cell_padding` (px, default 8), `border_color`, and `grid_borders`: `all` (default), `rows` (no lines between columns) or `columns` (no lines between rows). This is for fields, not tables; a table has its own borders. |
| `page_break` | `true` starts a new page before the section. |
| `keep_together` | `true` keeps the section on one page. |
| `visible_if` | Python expression on `doc`, for example `doc.discount_amount > 0`. |
| `custom_style` | Extra CSS declarations for the section. |

## Fields

Every field is a dict in a column's `fields`. Every block that is not a DocType field (Static Text, HTML, Divider, Spacer, Image, Barcode, Repeater) carries `"custom": 1` and a `fieldname` that is unique in the layout. `label` is optional for these.

### Props every field takes

| Key | Value |
| --- | --- |
| `fieldname`, `fieldtype`, `label` | For a DocType field, copy `fieldname` and `fieldtype` from the DocType meta. `label` is the printed label, so write your own or copy the meta label. |
| `show_label` | `show` (default), `hide`, or `inline` (label beside the value). |
| `align` | `left`, `center` or `right`. |
| `font_size` | px. |
| `bold` | `true` for bold. |
| `label_color`, `value_color` | Hex colours like `#1a5fb4`. |
| `hide_colon` | `true` drops the colon after the label when the format shows colons (`show_label_colon`). |
| `label_justify`, `label_gap` | Label placement and gap (px) when the label is beside the value. |
| `show_empty` | `true` prints the label even when the value is empty. |
| `date_format` | For Date and Datetime fields, for example `dd-mm-yyyy`. |
| `allow_page_break` | `true` lets a long text field split across pages. |
| `visible_if` | Python expression on `doc`. |
| `custom_style` | Extra CSS declarations, for example `"margin-top: 8px; color: #555;"`. |

### Field types

| `fieldtype` | Props | Prints |
| --- | --- | --- |
| Any DocType field type | `fieldname` of the document | The formatted value, through `doc.get_formatted`. |
| `Linked Field` | `link_path: "customer.customer_group"` | A field of the linked document, one hop. Respects permissions. |
| `Static Text` | `text` | Fixed text. `{fieldname}` and `{link_field.fieldname}` in the text become the document's values, for example `"Invoice {name} for {customer_name}"`. `{name}` is the document name. New lines print as line breaks. |
| `HTML` | `html` | A Jinja template rendered with `doc` and the `global_variables` names. Use it for anything the other blocks cannot express. Not printable with Typst. |
| `Table` | `fieldname` and `options` of the child table, `table_columns` | The child table. See below. |
| `Repeater` | `source` (child table fieldname), `repeater_columns` | Child rows with your own cell text. Each column: `template` (list of `{"t": "f", "v": "<fieldname>"}` for a value or `{"t": "t", "v": "text"}` for text), `align`, `color` (hex), `width` (percent). |
| `Image` | `image_url`, `width` (CSS length like `40mm`) | A fixed image, or the field's own image value. |
| `Barcode` | `barcode_format` (`CODE128`, `CODE39` or `QR`), `barcode_field` or `barcode_value`, `show_text`, `width` | A barcode or QR code of a field or a fixed value. |
| `Divider` | `custom_style` | A horizontal line. |
| `Spacer` | `height` (px) | Vertical space. |
| `Field Template` | `field_template` (a Print Format Field Template) | A shared template. |
| `Typst` | `typst` | Raw Typst markup. Typst renderer only. |

### Tables

```json
{
	"fieldname": "items", "fieldtype": "Table", "options": "Sales Invoice Item", "label": "Items",
	"table_columns": [
		{"fieldname": "item_name", "fieldtype": "Data", "label": "Item", "width": 50},
		{"fieldname": "qty", "fieldtype": "Float", "label": "Qty", "width": 15},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 35}
	],
	"table_style": "lined", "table_bordered": true, "table_header": "styled"
}
```

| Key | Value |
| --- | --- |
| `table_columns` | Columns in order. `width` is a percent. A column takes `date_format`, `column_condition` (Python on `doc`, hides the column), and `merged_fields` (more fields stacked in the same cell, with `merge_direction` and `image_size`). |
| `table_style`, `table_bordered` | Together they set the look the editor offers. Grid (every cell boxed): `lined` and `true`. Rows (lines between rows only): `lined` and `false`. Striped: `striped` and `false`. None: `plain` and `false`. Defaults are `lined` and `true`. |
| `table_header` | `styled` (default, shaded), `plain`, or `none` (no header row). |
| `table_header_bg`, `table_border_color` | CSS colours. |
| `table_cell_padding`, `table_radius`, `table_min_height` | px. |
| `row_condition` | Python on `row` and `doc`, for example `row.qty > 0`. Rows where it is false are left out. |

A column with no value in any row is left out of the print, and the remaining widths are scaled to 100%.

## A full example

```json
{
	"global_variables": "{% set customer_group = frappe.db.get_value('Customer', doc.customer, 'customer_group') or '' %}",
	"header": {"columns": [
		{"width": 1, "fields": [{"fieldname": "company", "fieldtype": "Link", "label": "Company", "show_label": "hide", "bold": true, "font_size": 18}]},
		{"width": 1, "fields": [{"fieldname": "title_text", "fieldtype": "Static Text", "custom": 1, "text": "Invoice {name}", "align": "right"}]}
	]},
	"sections": [
		{"label": "", "columns": [
			{"width": 1, "fields": [
				{"fieldname": "customer_name", "fieldtype": "Data", "label": "Customer"},
				{"fieldname": "customer_group_html", "fieldtype": "HTML", "custom": 1, "html": "<div>{{ customer_group }}</div>"}
			]},
			{"width": 1, "fields": [
				{"fieldname": "posting_date", "fieldtype": "Date", "label": "Date", "align": "right"}
			]}
		]},
		{"label": "", "columns": [{"fields": [
			{"fieldname": "items", "fieldtype": "Table", "options": "Sales Invoice Item", "label": "Items", "show_label": "hide",
			 "table_columns": [
				{"fieldname": "item_name", "fieldtype": "Data", "label": "Item", "width": 60},
				{"fieldname": "qty", "fieldtype": "Float", "label": "Qty", "width": 15},
				{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 25}
			 ]}
		]}]},
		{"label": "", "columns": [{"width": 1, "fields": []}, {"width": 1, "fields": [
			{"fieldname": "net_total", "fieldtype": "Currency", "label": "Net Total", "show_label": "inline", "align": "right"},
			{"fieldname": "grand_total", "fieldtype": "Currency", "label": "Grand Total", "show_label": "inline", "align": "right", "bold": true}
		]}]}
	],
	"footer": {"columns": [{"fields": [
		{"fieldname": "footer_note", "fieldtype": "Static Text", "custom": 1, "text": "Thank you for your business.", "align": "center"}
	]}]},
	"page": {"size": "A4", "orientation": "Portrait"}
}
```
