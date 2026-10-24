"""Seed the field-coverage DocType: one field of every fieldtype, for walking the field controls.

Creates three custom DocTypes in the `Custom` module, a Side Panel Form Layout, and one record:

- `Field Coverage`: every fieldtype on a few tabs, a read-only twin of each value field, and
  two hidden fields.
- `Field Coverage Row`: the child table, every value fieldtype it allows, all in the grid.
- `Field Coverage Row Text`, `… Numbers`, `… Choices`, `… Media`: the same fields, with about
  ten in the grid each, so a grid cell is wide enough to judge.
- `Field Coverage Tag`: the Table MultiSelect child, one Link.
- `COV C39 field coverage commits`: a Client Script that logs each field's commit as
  `[C39] <fieldname> <value>`, each row field's as `[C39] <table>.<fieldname> <value>`, and
  each Table MultiSelect change as `[C39] tags.onAdd <values>` or `tags.onRemove`.

Each run deletes what an earlier run made and makes it again, so the record starts from the
same values. Run it from the bench's `sites` folder with the bench's Python:

    cd sites && ../env/bin/python ../apps/frappe/frontend/walks/seed_field_coverage.py desk.localhost

It prints the record's name. `--delete` removes everything and makes nothing.
"""

import base64
import struct
import sys
import zlib

import frappe

PARENT = "Field Coverage"
ROW = "Field Coverage Row"

# The narrow tables: (table fieldname, child DocType, the fields in its grid).
ROW_GROUPS = [
	(
		"rows_text",
		"Field Coverage Row Text",
		[
			"data",
			"data_email",
			"data_url",
			"data_phone",
			"phone",
			"password",
			"read_only_value",
			"small_text",
			"text_editor",
		],
	),
	(
		"rows_numbers",
		"Field Coverage Row Numbers",
		[
			"int_value",
			"long_int",
			"float_value",
			"currency",
			"currency_value",
			"percent",
			"check",
			"rating",
			"duration",
		],
	),
	(
		"rows_choices",
		"Field Coverage Row Choices",
		[
			"select_value",
			"autocomplete",
			"link",
			"link_doctype",
			"dynamic_link",
			"date_value",
			"datetime_value",
			"time_value",
		],
	),
	(
		"rows_media",
		"Field Coverage Row Media",
		[
			"attach",
			"attach_image",
			"signature",
			"barcode",
			"color",
			"icon",
			"code",
			"json_value",
			"row_button",
		],
	),
]
TAG = "Field Coverage Tag"
MODULE = "Custom"
LINK_TARGET = "CRM Deal"
COMMIT_SCRIPT = "COV C39 field coverage commits"

DATA_OPTIONS = ["Email", "URL", "Phone", "Name", "IBAN", "Barcode"]


def png(rgb: tuple[int, int, int], size: int = 16) -> bytes:
	"""A solid square, so the image fields have a real file without a binary in the repo."""

	def chunk(kind: bytes, data: bytes) -> bytes:
		body = kind + data
		return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

	row = b"\x00" + bytes(rgb) * size
	header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
	return (
		b"\x89PNG\r\n\x1a\n"
		+ chunk(b"IHDR", header)
		+ chunk(b"IDAT", zlib.compress(row * size))
		+ chunk(b"IEND", b"")
	)


def field(fieldtype: str, fieldname: str, label: str | None = None, **props) -> dict:
	return {"fieldtype": fieldtype, "fieldname": fieldname, "label": label or fieldtype, **props}


def break_(fieldtype: str, fieldname: str, label: str | None = None) -> dict:
	return {"fieldtype": fieldtype, "fieldname": fieldname, "label": label}


def value_fields(prefix: str = "") -> list[dict]:
	"""Every value fieldtype once, plus Data once per option. `prefix` names the read-only twins."""
	f = lambda fieldtype, fieldname, label=None, **props: field(  # noqa: E731
		fieldtype, prefix + fieldname, (label or fieldtype) + (" (read only)" if prefix else ""), **props
	)
	return [
		f("Data", "data"),
		*[f("Data", f"data_{option.lower()}", f"Data {option}", options=option) for option in DATA_OPTIONS],
		f("Phone", "phone"),
		f("Password", "password"),
		f("Read Only", "read_only_value", "Read Only"),
		f("Small Text", "small_text"),
		f("Text", "text"),
		f("Long Text", "long_text"),
		f("Int", "int_value", "Int"),
		f("Long Int", "long_int"),
		f("Float", "float_value", "Float"),
		f("Link", "currency", "Currency code", options="Currency"),
		f("Currency", "currency_value", "Currency", options=prefix + "currency"),
		f("Percent", "percent"),
		f("Check", "check"),
		f("Rating", "rating"),
		f("Duration", "duration"),
		f("Select", "select_value", "Select", options="\nAlpha\nBeta\nGamma"),
		f("Autocomplete", "autocomplete", options="Red\nGreen\nBlue"),
		f("Link", "link", options=LINK_TARGET),
		f("Link", "link_doctype", "Dynamic Link target", options="DocType"),
		f("Dynamic Link", "dynamic_link", options=prefix + "link_doctype"),
		f("Table MultiSelect", "tags", "Table MultiSelect", options=TAG),
		f("Date", "date_value", "Date"),
		f("Datetime", "datetime_value", "Datetime"),
		f("Time", "time_value", "Time"),
		f("Text Editor", "text_editor"),
		f("Code", "code", options="Python"),
		f("JSON", "json_value", "JSON"),
		f("Markdown Editor", "markdown"),
		f("HTML Editor", "html_editor"),
		f("Attach", "attach"),
		f("Attach Image", "attach_image"),
		f("Image", "image", options=prefix + "attach_image"),
		f("Signature", "signature"),
		f("Barcode", "barcode"),
		f("Color", "color"),
		f("Icon", "icon"),
		f("Geolocation", "geolocation"),
	]


def parent_fields() -> list[dict]:
	values = {d["fieldname"]: d for d in value_fields()}
	pick = lambda *names: [values[name] for name in names]  # noqa: E731
	return [
		break_("Section Break", "text_section", "Text"),
		*pick("data", *[f"data_{o.lower()}" for o in DATA_OPTIONS]),
		break_("Column Break", "text_column"),
		*pick("phone", "password", "read_only_value", "small_text", "text", "long_text"),
		break_("Section Break", "number_section", "Numbers"),
		*pick("int_value", "long_int", "float_value", "currency", "currency_value", "percent"),
		break_("Column Break", "number_column"),
		*pick("check", "rating", "duration"),
		break_("Section Break", "choice_section", "Choices"),
		*pick("select_value", "autocomplete", "link"),
		break_("Column Break", "choice_column"),
		*pick("link_doctype", "dynamic_link", "tags"),
		break_("Section Break", "date_section", "Dates"),
		*pick("date_value", "datetime_value", "time_value"),
		field("Data", "hidden_data", "Hidden Data", hidden=1),
		field("Link", "hidden_link", "Hidden Link", options=LINK_TARGET, hidden=1),
		break_("Tab Break", "rich_tab", "Rich text"),
		*pick("text_editor", "code", "json_value", "markdown", "html_editor"),
		field("HTML", "html_block", "HTML", options="<p>A static <b>HTML</b> block.</p>"),
		field("Heading", "heading", "Heading"),
		field("Button", "button", "Button"),
		break_("Tab Break", "media_tab", "Media"),
		*pick("attach", "attach_image", "image", "signature"),
		break_("Column Break", "media_column"),
		*pick("barcode", "color", "icon", "geolocation"),
		field("Attachment Gallery", "gallery", "Attachment Gallery"),
		field("Fold", "fold", "Fold"),
		break_("Section Break", "after_fold_section", "After the fold"),
		field("Data", "after_fold", "Data after the fold"),
		break_("Tab Break", "table_tab", "Table"),
		field("Table", "rows", "Table, every column", options=ROW),
		*[
			field("Table", table, f"Table, {child.split()[-1].lower()}", options=child)
			for table, child, _ in ROW_GROUPS
		],
		break_("Tab Break", "read_only_tab", "Read only"),
		*[{**d, "read_only": 1} for d in value_fields(prefix="ro_") if d["fieldtype"] != "Table MultiSelect"],
	]


def row_fields(in_grid: list[str] | None = None) -> list[dict]:
	"""Every value field a row allows; all of them in the grid unless `in_grid` names some."""
	# A Table cannot nest a Table MultiSelect, and Image is display-only.
	skip = {"Table MultiSelect", "Image"}
	fields = [d for d in value_fields() if d["fieldtype"] not in skip]
	fields.append(field("Button", "row_button", "Button"))
	return [{**d, "in_list_view": int(in_grid is None or d["fieldname"] in in_grid)} for d in fields]


def make_doctype(name: str, fields: list[dict], **props) -> None:
	# `Long Int` is a database type the DocField select does not list, so the field is
	# inserted as `Int` and switched after, with its column.
	long_ints = [d["fieldname"] for d in fields if d["fieldtype"] == "Long Int"]
	doc = frappe.new_doc("DocType")
	doc.update({"name": name, "module": MODULE, "custom": 1, **props})
	for d in fields:
		doc.append("fields", {**d, "fieldtype": "Int"} if d["fieldname"] in long_ints else d)
	if not props.get("istable"):
		doc.append("permissions", {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1})
	doc.insert()
	if long_ints:
		frappe.db.set_value(
			"DocField", {"parent": name, "fieldname": ("in", long_ints)}, "fieldtype", "Long Int"
		)
		frappe.clear_cache(doctype=name)
		frappe.db.updatedb(name)


def make_file(filename: str, content: bytes) -> str:
	file = frappe.get_doc({"doctype": "File", "file_name": filename, "content": content, "is_private": 0})
	file.insert()
	return file.file_url


def record_values() -> dict:
	deal, other_deal = frappe.get_all(LINK_TARGET, pluck="name", order_by="creation asc", limit=2)
	signature = "data:image/png;base64," + base64.b64encode(png((40, 40, 40))).decode()
	values = {
		"data": "Plain data",
		"data_email": "ada@example.com",
		"data_url": "https://frappe.io",
		"data_phone": "+91-9876543210",
		"data_name": "Ada Lovelace",
		"data_iban": "GB82WEST12345698765432",
		"data_barcode": "4006381333931",
		"phone": "+91-9876543210",
		"password": "s3cret-value",
		"read_only_value": "Set by the seed",
		"small_text": "Small text,\non two lines",
		"text": "Text,\non two lines",
		"long_text": "Long text,\non two lines",
		"int_value": 42,
		"long_int": 9007199254740991,
		"float_value": 3.14159,
		"currency": "EUR",
		"currency_value": 1234567.89,
		"percent": 12.5,
		"check": 1,
		"rating": 0.6,
		"duration": 93784,
		"select_value": "Beta",
		"autocomplete": "Green",
		"link": deal,
		"link_doctype": LINK_TARGET,
		"dynamic_link": other_deal,
		"date_value": "2026-10-24",
		"datetime_value": "2026-10-24 14:30:00",
		"time_value": "09:15:00",
		"text_editor": "<p>Hello <strong>world</strong>, a <em>Text Editor</em> value.</p>",
		"code": "def greet(name):\n\treturn f'Hello {name}'\n",
		"json_value": '{\n\t"a": 1,\n\t"b": [true, null]\n}',
		"markdown": "# A heading\n\n- one\n- two\n",
		"html_editor": "<div class='box'>Some <b>HTML</b></div>",
		"attach": make_file("field-coverage.txt", b"A text file the Attach field points at.\n"),
		"attach_image": make_file("field-coverage.png", png((230, 90, 40))),
		"signature": signature,
		"barcode": "4006381333931",
		"color": "#3b82f6",
		"icon": "star",
		"geolocation": '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},'
		'"geometry":{"type":"Point","coordinates":[72.8777,19.076]}}]}',
	}
	values["image"] = values["attach_image"]
	return values


def make_record() -> str:
	values = record_values()
	doc = frappe.new_doc(PARENT)
	doc.update(values)
	doc.update({"ro_" + key: value for key, value in values.items()})
	doc.update(
		{
			"ro_currency_value": values["currency_value"],
			"hidden_data": "Hidden value",
			"hidden_link": values["link"],
			"after_fold": "Below the fold",
		}
	)
	for deal in frappe.get_all(LINK_TARGET, pluck="name", order_by="creation asc", limit=2):
		doc.append("tags", {"deal": deal})
	row_names = {d["fieldname"] for d in row_fields()}
	for table in ["rows"] + [table for table, _, _ in ROW_GROUPS]:
		for n in (1, 2):
			row = {key: value for key, value in values.items() if key in row_names}
			row.update({"data": f"Row {n}", "int_value": n, "check": n % 2})
			doc.append(table, row)
	doc.insert()
	return doc.name


def make_panel_layout() -> None:
	"""A Side Panel row with every value field, so the panel shows each control."""
	names = [d["fieldname"] for d in value_fields()]
	half = len(names) // 2
	layout = [
		{
			"sections": [
				{"name": "fields_a", "label": "Fields A", "columns": [{"fields": names[:half]}]},
				{"name": "fields_b", "label": "Fields B", "columns": [{"fields": names[half:]}]},
				{
					"name": "read_only",
					"label": "Read only",
					"columns": [{"fields": ["ro_" + n for n in names[:6]]}],
				},
			]
		}
	]
	frappe.get_doc(
		{"doctype": "Form Layout", "dt": PARENT, "type": "Side Panel", "layout": frappe.as_json(layout)}
	).insert()


def make_commit_script() -> None:
	"""The battery row a walk reads: one console line per commit, so a missing or doubled one shows."""
	log = "console.log('[C39] {key}', JSON.stringify({value}))"
	# A Table MultiSelect's vocabulary is its rows' add and remove, as a table's is.
	top = [d["fieldname"] for d in value_fields() if d["fieldtype"] not in ("Image", "Table MultiSelect")]
	rows = [d["fieldname"] for d in row_fields() if d["fieldtype"] != "Button"]
	lines = [f"\t{name}(page) {{ {log.format(key=name, value=f'page.doc.{name}')} }}," for name in top]
	lines.append("\ttags: {")
	lines += [
		f"\t\t{event}(page) {{ {log.format(key='tags.' + event, value='page.doc.tags.map((t) => t.deal)')} }},"
		for event in ("onAdd", "onRemove")
	]
	lines.append("\t},")
	for table in ["rows"] + [table for table, _, _ in ROW_GROUPS]:
		lines.append(f"\t{table}: {{")
		lines += [
			f"\t\t{name}(page, row) {{ {log.format(key=f'{table}.{name}', value=f'row?.doc?.{name} ?? row')} }},"
			for name in rows
		]
		lines.append("\t},")
	script = "// C39 — every field's commit on Field Coverage, one console line each.\n"
	script += "export default {\n" + "\n".join(lines) + "\n}\n"
	frappe.get_doc(
		{
			"doctype": "Client Script",
			"name": COMMIT_SCRIPT,
			"__newname": COMMIT_SCRIPT,
			"dt": PARENT,
			"view": "Record",
			"enabled": 1,
			"script": script,
		}
	).insert()


def delete_all() -> None:
	if frappe.db.exists("DocType", PARENT):
		for name in frappe.get_all(PARENT, pluck="name"):
			frappe.delete_doc(PARENT, name, force=1)
	frappe.db.delete("Form Layout", {"dt": PARENT})
	frappe.db.delete("Client Script", {"name": COMMIT_SCRIPT})
	frappe.db.delete("File", {"file_name": ("in", ["field-coverage.txt", "field-coverage.png"])})
	for doctype in (PARENT, ROW, *[child for _, child, _ in ROW_GROUPS], TAG):
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, force=1)


def seed() -> str:
	delete_all()
	make_doctype(TAG, [field("Link", "deal", "Deal", options=LINK_TARGET, in_list_view=1)], istable=1)
	make_doctype(ROW, row_fields(), istable=1)
	for _, child, in_grid in ROW_GROUPS:
		make_doctype(child, row_fields(in_grid), istable=1)
	make_doctype(PARENT, parent_fields(), autoname="hash")
	make_panel_layout()
	make_commit_script()
	return make_record()


def main() -> None:
	site = next((arg for arg in sys.argv[1:] if not arg.startswith("--")), None)
	if not site:
		sys.exit("Usage: seed_field_coverage.py <site> [--delete]")
	frappe.init(site=site, sites_path=".")
	frappe.connect()
	# A dev-only script run by hand on a local site: it acts as Administrator to create DocTypes.
	frappe.set_user("Administrator")  # nosemgrep
	try:
		if "--delete" in sys.argv:
			delete_all()
			print(f"Deleted {PARENT}")
		else:
			print(f"{PARENT} {seed()}")
		# A standalone script, not a request: nothing else commits its transaction.
		frappe.db.commit()  # nosemgrep
	finally:
		frappe.destroy()


if __name__ == "__main__":
	main()
