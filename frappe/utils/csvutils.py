# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import csv
import json
from io import StringIO

import requests

import frappe
from frappe import _, msgprint
from frappe.utils import cint, comma_or, cstr, flt


def read_csv_content_from_attached_file(doc):
	"""
	Retrieve the content of a CSV file attached to a document.

	This function queries the File doctype to find the most recent attached file for
	the specified document. If found, it retrieves the content of the file and
	passes it to the read_csv_content function. If the file is not found, it
	displays a message and raises an exception.

	Args:
	    doc: The document for which to retrieve the attached file content.

	Raises:
	    Exception: If the file is not found.
	"""
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


def read_csv_content(fcontent):
	"""
	Read the content of a CSV file and return the parsed data as a list of rows.

	Args:
	    fcontent (str): The content of the CSV file.

	Returns:
	    list: The parsed data as a list of rows, where each row is a list of values.

	Raises:
	    Exception: If the input content is not a valid CSV file.
	"""
	if not isinstance(fcontent, str):
	    decoded = False
	    for encoding in ["utf-8", "windows-1250", "windows-1252"]:
	        try:
	            fcontent = str(fcontent, encoding)
	            decoded = True
	            break
	        except UnicodeDecodeError:
	            continue

	    if not decoded:
	        frappe.msgprint(
	        	_("Unknown file encoding. Tried utf-8, windows-1250, windows-1252."), raise_exception=True
	        )

	fcontent = fcontent.encode("utf-8")
	content = [frappe.safe_decode(line) for line in fcontent.splitlines(True)]

	try:
	    rows = []
	    for row in csv.reader(content):
	        r = []
	        for val in row:
	            # decode everything
	            val = val.strip()

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
def send_csv_to_client(args):
	"""
	Send a CSV response to the client.

	This function takes a JSON string as an argument and converts it to a
	dictionary. It sets the necessary response fields and calls the 'to_csv'
	function to convert the data to CSV format.

	Args:
	    args (str): A JSON string containing the data and filename.
	"""
	if isinstance(args, str):
	    args = json.loads(args)

	args = frappe._dict(args)

	frappe.response["result"] = cstr(to_csv(args.data))
	frappe.response["doctype"] = args.filename
	frappe.response["type"] = "csv"


def to_csv(data):
	"""
	Convert a list of rows to CSV format.

	This function takes a list of rows as input and uses the 'UnicodeWriter' class
	to write the rows to a CSV file.

	Args:
	    data (list): A list of rows to be converted to CSV format.

	Returns:
	    str: The CSV data.
	"""
	writer = UnicodeWriter()
	for row in data:
	    writer.writerow(row)

	return writer.getvalue()


def build_csv_response(data, filename):
	"""
	Build a CSV response.

	This function takes the data and filename as separate arguments and sets the
	necessary response fields.

	Args:
	    data (list): A list of rows to be converted to CSV format.
	    filename (str): The filename for the CSV file.
	"""
	frappe.response["result"] = cstr(to_csv(data))
	frappe.response["doctype"] = filename
	frappe.response["type"] = "csv"


class UnicodeWriter:
	"""
	A utility class for writing Unicode rows to a CSV file.

	This class provides methods for writing Unicode rows to a CSV file. It is used
	by the 'to_csv' function.
	"""
	def __init__(self, encoding="utf-8", quoting=csv.QUOTE_NONNUMERIC):
	    self.encoding = encoding
	    self.queue = StringIO()
	    self.writer = csv.writer(self.queue, quoting=quoting)

	def writerow(self, row):
	    self.writer.writerow(row)

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
	                	_("{0} must be one of {1}").format(_(docfield.label), comma_or(docfield.options.split("\n")))
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
	"""Returns an HTML link to the specified document"""
	return '<a href="/app/Form/%(doctype)s/%(name)s">%(name)s</a>' % locals()


def get_csv_content_from_google_sheets(url):
	"""
	Retrieves the content of a CSV file from a Google Sheets URL.

	This function takes a Google Sheets URL as input, validates the URL using the
	'validate_google_sheets_url' function, extracts the sheet id (gid) from
	the URL, and constructs a new URL with the gid and a CSV export format.
	It then sends a GET request to the constructed URL and returns the response
	content if the request is successful.
	If the response indicates an error, the function raises appropriate exceptions.

	Args:
	    url (str): The Google Sheets URL.

	Returns:
	    bytes: The content of the CSV file.

	Raises:
	    frappe.ValidationError: If the Google Sheets URL is invalid or not publicly accessible.
	    frappe.ValidationError: If the Google Sheets URL does not have the required format.
	    requests.exceptions.HTTPError: If the request to the Google Sheets URL fails.
	"""
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
	"""
	Validates whether a given URL is a valid Google Sheets URL.

	This function validates whether a given URL is a valid Google Sheets URL
	by checking the scheme, domain, and path of the URL.

	Args:
	    url (str): The URL to be validated.

	Raises:
	    frappe.ValidationError: If the URL is not a valid Google Sheets URL.
	"""
	from urllib.parse import urlparse

	u = urlparse(url)
	if u.scheme != "https" or u.netloc != "docs.google.com" or "/spreadsheets/" not in u.path:
	    frappe.throw(
	    	_('"{0}" is not a valid Google Sheets URL').format(url),
	    	title=_("Invalid URL"),
	    )
