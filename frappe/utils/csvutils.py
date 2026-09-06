# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import csv
import json
from csv import Sniffer
from io import StringIO
from typing import Any

import requests

import frappe
from frappe import _, msgprint
from frappe.core.doctype.file.file import FILE_ENCODING_OPTIONS
from frappe.utils import cint, comma_or, cstr, flt

# leading characters that spreadsheet applications treat as the start of a formula
FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def escape_formula_injection(value):
	"""Prefix a leading single quote so spreadsheet apps render, but don't evaluate, formula-like strings."""
	if isinstance(value, str) and value.startswith(FORMULA_TRIGGER_CHARS):
		return "'" + value
	return value


def unescape_formula_injection(value):
	"""Reverse escape_formula_injection on the way back in via CSV import.

	A leading single quote in front of a formula-trigger character is a display-only
	marker, not part of the value, so re-importing our own export must not bake it in
	permanently (e.g. phone numbers, negative quantities stored as text).

	Trade-off: a value that genuinely starts with a quote, e.g. "'+S-001", loses that
	quote too - CSV has no way to tell the two cases apart. Assumes the input came from
	escape_formula_injection, not an arbitrary external CSV.
	"""
	if (
		isinstance(value, str)
		and len(value) > 1
		and value[0] == "'"
		and value[1:].startswith(FORMULA_TRIGGER_CHARS)
	):
		return value[1:]
	return value


def read_csv_content_from_attached_file(doc):
	fileid = frappe.get_all(
		"File",
		fields=["name"],
		filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
		order_by="creation desc",
	)

	if fileid:
		fileid = fileid[0].name

	if not fileid:
		msgprint(_("File not attached"))
		raise Exception

	try:
		_file = frappe.get_doc("File", fileid)
		fcontent = _file.get_content()
		return read_csv_content(fcontent)
	except Exception:
		frappe.throw(
			_("Unable to open attached file. Did you export it as CSV?"), title=_("Invalid CSV Format")
		)


def read_csv_content(fcontent, use_sniffer: bool = False):
	if not isinstance(fcontent, str):
		decoded = False
		for encoding in FILE_ENCODING_OPTIONS:
			try:
				fcontent = str(fcontent, encoding)
				decoded = True
				break
			except UnicodeDecodeError:
				continue

		if not decoded:
			frappe.msgprint(
				_("Unknown file encoding. Tried to use: {0}").format(", ".join(FILE_ENCODING_OPTIONS)),
				raise_exception=True,
			)

	fcontent = fcontent.encode("utf-8")
	content = [frappe.safe_decode(line) for line in fcontent.splitlines(True)]
	dialect = csv.get_dialect("excel")

	if use_sniffer:
		sniffer = Sniffer()
		# Don't need to use whole csv, if more than 20 rows, use just first 20
		sample_content = content[:20] if len(content) > 20 else content
		# only testing for most common delimiter types, this later can be extended
		# init default dialect, to avoid lint errors
		try:
			# csv by default uses excel dialect, which is not always correct
			dialect = sniffer.sniff(
				sample="\n".join(sample_content), delimiters=frappe.flags.delimiter_options
			)
		except csv.Error:
			# if sniff fails, show alert on user interface. Fall back to use default dialect (excel)
			frappe.msgprint(
				_(
					"Delimiter detection failed. Try to enable custom delimiters and adjust the delimiter options as per your data."
				),
				indicator="orange",
				alert=True,
			)

	try:
		rows = []
		for row in csv.reader(content, dialect=dialect):
			r = []
			for val in row:
				# decode everything
				val = unescape_formula_injection(val.strip())

				if val == "":
					# reason: in maraidb strict config, one cannot have blank strings for non string datatypes
					r.append(None)
				else:
					r.append(val)

			rows.append(r)

		return rows

	except Exception:
		frappe.msgprint(_("Not a valid Comma Separated Value (CSV File)"))
		raise


@frappe.whitelist()
def send_csv_to_client(args: str | dict[str, Any]):
	if isinstance(args, str):
		args = json.loads(args)

	args = frappe._dict(args)

	frappe.response["result"] = cstr(to_csv(args.data))
	frappe.response["doctype"] = args.filename
	frappe.response["type"] = "csv"


def to_csv(data):
	writer = UnicodeWriter()
	for row in data:
		writer.writerow(row)

	return writer.getvalue()


def build_csv_response(data, filename):
	frappe.response["result"] = cstr(to_csv(data))
	frappe.response["doctype"] = filename
	frappe.response["type"] = "csv"


class UnicodeWriter:
	def __init__(self, encoding="utf-8", quoting=csv.QUOTE_NONNUMERIC):
		self.encoding = encoding
		self.queue = StringIO()
		self.writer = csv.writer(self.queue, quoting=quoting)

	def writerow(self, row):
		self.writer.writerow([escape_formula_injection(v) for v in row])

	def getvalue(self):
		return self.queue.getvalue()


def check_record(d):
	"""check for mandatory, select options, dates. these should ideally be in doclist"""
	from frappe.utils.dateutils import parse_date

	doc = frappe.get_doc(d)

	for key in d:
		docfield = doc.meta.get_field(key)
		val = d[key]
		if docfield:
			if docfield.reqd and (val == "" or val is None):
				frappe.msgprint(_("{0} is required").format(docfield.label), raise_exception=1)

			if docfield.fieldtype == "Select" and val and docfield.options:
				if val not in docfield.options.split("\n"):
					frappe.throw(
						_("{0} must be one of {1}").format(
							_(docfield.label, context=docfield.parent), comma_or(docfield.options.split("\n"))
						)
					)

			if val and docfield.fieldtype == "Date":
				d[key] = parse_date(val)
			elif val and docfield.fieldtype in ["Int", "Check"]:
				d[key] = cint(val)
			elif val and docfield.fieldtype in ["Currency", "Float", "Percent"]:
				d[key] = flt(val)


def import_doc(d, doctype, overwrite, row_idx, submit=False, ignore_links=False):
	"""import main (non child) document"""
	if d.get("name") and frappe.db.exists(doctype, d["name"]):
		if overwrite:
			doc = frappe.get_doc(doctype, d["name"])
			doc.flags.ignore_links = ignore_links
			doc.update(d)
			if d.get("docstatus") == 1:
				doc.update_after_submit()
			elif d.get("docstatus") == 0 and submit:
				doc.submit()
			else:
				doc.save()
			return "Updated row (#%d) %s" % (row_idx + 1, getlink(doctype, d["name"]))
		else:
			return "Ignored row (#%d) %s (exists)" % (row_idx + 1, getlink(doctype, d["name"]))
	else:
		doc = frappe.get_doc(d)
		doc.flags.ignore_links = ignore_links
		doc.insert()

		if submit:
			doc.submit()

		return "Inserted row (#%d) %s" % (row_idx + 1, getlink(doctype, doc.get("name")))


def getlink(doctype, name):
	return '<a href="/desk/Form/{doctype}/{name}">{name}</a>'.format(**locals())


def get_csv_content_from_google_sheets(url):
	# https://docs.google.com/spreadsheets/d/{sheetid}}/edit#gid={gid}
	validate_google_sheets_url(url)
	# get gid, defaults to first sheet
	if "gid=" in url:
		gid = url.rsplit("gid=", 1)[1]
	else:
		gid = 0
	# remove /edit path
	url = url.rsplit("/edit", 1)[0]
	# add /export path,
	url = url + f"/export?format=csv&gid={gid}"

	headers = {"Accept": "text/csv"}
	response = requests.get(url, headers=headers)

	if response.ok:
		# if it returns html, it couldn't find the CSV content
		# because of invalid url or no access
		if response.text.strip().endswith("</html>"):
			frappe.throw(
				_("Google Sheets URL is invalid or not publicly accessible."), title=_("Invalid URL")
			)
		return response.content
	elif response.status_code == 400:
		frappe.throw(
			_(
				'Google Sheets URL must end with "gid={number}". Copy and paste the URL from the browser address bar and try again.'
			),
			title=_("Incorrect URL"),
		)
	else:
		response.raise_for_status()


def validate_google_sheets_url(url):
	from urllib.parse import urlparse

	u = urlparse(url)
	if u.scheme != "https" or u.netloc != "docs.google.com" or "/spreadsheets/" not in u.path:
		frappe.throw(
			_('"{0}" is not a valid Google Sheets URL').format(url),
			title=_("Invalid URL"),
		)
