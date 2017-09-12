# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

from six.moves import range
import requests
import frappe, json, os
import frappe.permissions
import frappe.async

from frappe import _

from frappe.utils.csvutils import getlink
from frappe.utils.dateutils import parse_date
from frappe.utils.file_manager import save_url

from frappe.utils import cint, cstr, flt, getdate, get_datetime, get_url
from frappe.core.page.data_import_tool.data_import_tool import get_data_keys
from six import text_type, string_types

@frappe.whitelist()
def upload(rows = None, submit_after_import=None, ignore_encoding_errors=False, no_email=True, overwrite=None,
	update_only = None, ignore_links=False, pre_process=None, via_console=False, from_data_import="No"):
	"""upload data"""

	frappe.flags.in_import = True

	# extra input params
	params = json.loads(frappe.form_dict.get("params") or '{}')


	if params.get("submit_after_import"):
		submit_after_import = True
	if params.get("ignore_encoding_errors"):
		ignore_encoding_errors = True
	if not params.get("no_email"):
		no_email = False
	if params.get('update_only'):
		update_only = True
	if params.get('from_data_import'):
		from_data_import = params.get('from_data_import')

	frappe.flags.mute_emails = no_email

	def get_data_keys_definition():
		return get_data_keys()

	def bad_template():
		frappe.throw(_("Please do not change the rows above {0}").format(get_data_keys_definition().data_separator))

	def check_data_length():
		max_rows = 5000
		if not data:
			frappe.throw(_("No data found"))
		elif not via_console and len(data) > max_rows:
			frappe.throw(_("Only allowed {0} rows in one import").format(max_rows))

	def get_start_row():
		for i, row in enumerate(rows):
			if row and row[0]==get_data_keys_definition().data_separator:
				return i+1
		bad_template()

	def get_header_row(key):
		return get_header_row_and_idx(key)[0]

	def get_header_row_and_idx(key):
		for i, row in enumerate(header):
			if row and row[0]==key:
				return row, i
		return [], -1

	def filter_empty_columns(columns):
		empty_cols = list(filter(lambda x: x in ("", None), columns))

		if empty_cols:
			if columns[-1*len(empty_cols):] == empty_cols:
				# filter empty columns if they exist at the end
				columns = columns[:-1*len(empty_cols)]
			else:
				frappe.msgprint(_("Please make sure that there are no empty columns in the file."),
					raise_exception=1)

		return columns

	def make_column_map():
		doctype_row, row_idx = get_header_row_and_idx(get_data_keys_definition().doctype)
		if row_idx == -1: # old style
			return

		dt = None
		for i, d in enumerate(doctype_row[1:]):
			if d not in ("~", "-"):
				if d and doctype_row[i] in (None, '' ,'~', '-', 'DocType:'):
					dt, parentfield = d, None
					# xls format truncates the row, so it may not have more columns
					if len(doctype_row) > i+2:
						parentfield = doctype_row[i+2]
					doctypes.append((dt, parentfield))
					column_idx_to_fieldname[(dt, parentfield)] = {}
					column_idx_to_fieldtype[(dt, parentfield)] = {}
				if dt:
					column_idx_to_fieldname[(dt, parentfield)][i+1] = rows[row_idx + 2][i+1]
					column_idx_to_fieldtype[(dt, parentfield)][i+1] = rows[row_idx + 4][i+1]

	def get_doc(start_idx):
		if doctypes:
			doc = {}
			for idx in range(start_idx, len(rows)):
				if (not doc) or main_doc_empty(rows[idx]):
					for dt, parentfield in doctypes:
						d = {}
						for column_idx in column_idx_to_fieldname[(dt, parentfield)]:
							try:
								fieldname = column_idx_to_fieldname[(dt, parentfield)][column_idx]
								fieldtype = column_idx_to_fieldtype[(dt, parentfield)][column_idx]

								d[fieldname] = rows[idx][column_idx]
								if fieldtype in ("Int", "Check"):
									d[fieldname] = cint(d[fieldname])
								elif fieldtype in ("Float", "Currency", "Percent"):
									d[fieldname] = flt(d[fieldname])
								elif fieldtype == "Date":
									if d[fieldname] and isinstance(d[fieldname], string_types):
										d[fieldname] = getdate(parse_date(d[fieldname]))
								elif fieldtype == "Datetime":
									if d[fieldname]:
										if " " in d[fieldname]:
											_date, _time = d[fieldname].split()
										else:
											_date, _time = d[fieldname], '00:00:00'
										_date = parse_date(d[fieldname])
										d[fieldname] = get_datetime(_date + " " + _time)
									else:
										d[fieldname] = None

								elif fieldtype in ("Image", "Attach Image", "Attach"):
									# added file to attachments list
									attachments.append(d[fieldname])

								elif fieldtype in ("Link", "Dynamic Link") and d[fieldname]:
									# as fields can be saved in the number format(long type) in data import template
									d[fieldname] = cstr(d[fieldname])

							except IndexError:
								pass

						# scrub quotes from name and modified
						if d.get("name") and d["name"].startswith('"'):
							d["name"] = d["name"][1:-1]

						if sum([0 if not val else 1 for val in d.values()]):
							d['doctype'] = dt
							if dt == doctype:
								doc.update(d)
							else:
								if not overwrite:
									d['parent'] = doc["name"]
								d['parenttype'] = doctype
								d['parentfield'] = parentfield
								doc.setdefault(d['parentfield'], []).append(d)
				else:
					break

			return doc
		else:
			doc = frappe._dict(zip(columns, rows[start_idx][1:]))
			doc['doctype'] = doctype
			return doc

	def main_doc_empty(row):
		return not (row and ((len(row) > 1 and row[1]) or (len(row) > 2 and row[2])))

	users = frappe.db.sql_list("select name from tabUser")
	def prepare_for_insert(doc):
		# don't block data import if user is not set
		# migrating from another system
		if not doc.owner in users:
			doc.owner = frappe.session.user
		if not doc.modified_by in users:
			doc.modified_by = frappe.session.user

	def is_valid_url(url):
		is_valid = False
		if url.startswith("/files") or url.startswith("/private/files"):
			url = get_url(url)

		try:
			r = requests.get(url)
			is_valid = True if r.status_code == 200 else False
		except Exception:
			pass

		return is_valid

	def attach_file_to_doc(doctype, docname, file_url):
		# check if attachment is already available
		# check if the attachement link is relative or not
		if not file_url:
			return
		if not is_valid_url(file_url):
			return

		files = frappe.db.sql("""Select name from `tabFile` where attached_to_doctype='{doctype}' and
			attached_to_name='{docname}' and (file_url='{file_url}' or thumbnail_url='{file_url}')""".format(
				doctype=doctype,
				docname=docname,
				file_url=file_url
			))

		if files:
			# file is already attached
			return

		save_url(file_url, None, doctype, docname, "Home/Attachments", 0)

	# header
	if not rows:
		from frappe.utils.file_manager import get_file_doc
		file_doc = get_file_doc(dt='', dn="Data Import", folder='Home', is_private=1)
		filename, file_extension = os.path.splitext(file_doc.file_name)

		if file_extension == '.xlsx' and from_data_import == 'Yes':
			from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
			rows = read_xlsx_file_from_attached_file(file_id=file_doc.name)

		elif file_extension == '.csv':
			from frappe.utils.file_manager import get_file
			from frappe.utils.csvutils import read_csv_content
			fname, fcontent = get_file(file_doc.name)
			rows = read_csv_content(fcontent, ignore_encoding_errors)

		else:
			frappe.throw(_("Unsupported File Format"))

	start_row = get_start_row()
	header = rows[:start_row]
	data = rows[start_row:]
	doctype = get_header_row(get_data_keys_definition().main_table)[1]
	columns = filter_empty_columns(get_header_row(get_data_keys_definition().columns)[1:])
	doctypes = []
	column_idx_to_fieldname = {}
	column_idx_to_fieldtype = {}
	attachments = []

	if submit_after_import and not cint(frappe.db.get_value("DocType",
			doctype, "is_submittable")):
		submit_after_import = False

	parenttype = get_header_row(get_data_keys_definition().parent_table)

	if len(parenttype) > 1:
		parenttype = parenttype[1]

	# check permissions
	if not frappe.permissions.can_import(parenttype or doctype):
		frappe.flags.mute_emails = False
		return {"messages": [_("Not allowed to Import") + ": " + _(doctype)], "error": True}

	# allow limit rows to be uploaded
	check_data_length()
	make_column_map()

	if overwrite==None:
		overwrite = params.get('overwrite')


	# delete child rows (if parenttype)
	parentfield = None
	if parenttype:
		parentfield = get_parent_field(doctype, parenttype)

		if overwrite:
			delete_child_rows(data, doctype)

	ret = []

	def log(msg):
		if via_console:
			print(msg.encode('utf-8'))
		else:
			ret.append(msg)

	def as_link(doctype, name):
		if via_console:
			return "{0}: {1}".format(doctype, name)
		else:
			return getlink(doctype, name)

	error = False
	total = len(data)
	for i, row in enumerate(data):
		# bypass empty rows
		if main_doc_empty(row):
			continue

		row_idx = i + start_row
		doc = None

		# publish task_update
		frappe.publish_realtime("data_import_progress", {"progress": [i, total]},
			user=frappe.session.user)

		try:
			doc = get_doc(row_idx)
			if pre_process:
				pre_process(doc)

			if parentfield:
				parent = frappe.get_doc(parenttype, doc["parent"])
				doc = parent.append(parentfield, doc)
				parent.save()
				log('Inserted row for %s at #%s' % (as_link(parenttype,
					doc.parent),text_type(doc.idx)))
			else:
				if overwrite and doc["name"] and frappe.db.exists(doctype, doc["name"]):
					original = frappe.get_doc(doctype, doc["name"])
					original_name = original.name
					original.update(doc)
					# preserve original name for case sensitivity
					original.name = original_name
					original.flags.ignore_links = ignore_links
					original.save()
					log('Updated row (#%d) %s' % (row_idx + 1, as_link(original.doctype, original.name)))
					doc = original
				else:
					if not update_only:
						doc = frappe.get_doc(doc)
						prepare_for_insert(doc)
						doc.flags.ignore_links = ignore_links
						doc.insert()
						log('Inserted row (#%d) %s' % (row_idx + 1, as_link(doc.doctype, doc.name)))
					else:
						log('Ignored row (#%d) %s' % (row_idx + 1, row[1]))
				if attachments:
					# check file url and create a File document
					for file_url in attachments:
						attach_file_to_doc(doc.doctype, doc.name, file_url)
				if submit_after_import:
					doc.submit()
					log('Submitted row (#%d) %s' % (row_idx + 1, as_link(doc.doctype, doc.name)))
		except Exception as e:
			error = True
			if doc:
				frappe.errprint(doc if isinstance(doc, dict) else doc.as_dict())
			err_msg = frappe.local.message_log and "\n\n".join(frappe.local.message_log) or cstr(e)
			log('Error for row (#%d) %s : %s' % (row_idx + 1,
				len(row)>1 and row[1] or "", err_msg))
			frappe.errprint(frappe.get_traceback())
		finally:
			frappe.local.message_log = []

	if error:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	frappe.flags.mute_emails = False
	frappe.flags.in_import = False

	return {"messages": ret, "error": error}

def get_parent_field(doctype, parenttype):
	parentfield = None

	# get parentfield
	if parenttype:
		for d in frappe.get_meta(parenttype).get_table_fields():
			if d.options==doctype:
				parentfield = d.fieldname
				break

		if not parentfield:
			frappe.msgprint(_("Did not find {0} for {0} ({1})").format("parentfield", parenttype, doctype))
			raise Exception

	return parentfield

def delete_child_rows(rows, doctype):
	"""delete child rows for all parents"""
	for p in list(set([r[1] for r in rows])):
		if p:
			frappe.db.sql("""delete from `tab{0}` where parent=%s""".format(doctype), p)
