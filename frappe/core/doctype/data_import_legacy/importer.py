#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

from six.moves import range
import requests
import frappe, json
import frappe.permissions

from frappe import _

from frappe.utils.csvutils import getlink
from frappe.utils.dateutils import parse_date

from frappe.utils import cint, cstr, flt, getdate, get_datetime, get_url, get_absolute_url, duration_to_seconds
from six import string_types


@frappe.whitelist()
def get_data_keys():
	return frappe._dict({
		"data_separator": _('Start entering data below this line'),
		"main_table": _("Table") + ":",
		"parent_table": _("Parent Table") + ":",
		"columns": _("Column Name") + ":",
		"doctype": _("DocType") + ":"
	})



@frappe.whitelist()
def upload(rows = None, submit_after_import=None, ignore_encoding_errors=False, no_email=True, overwrite=None,
	update_only = None, ignore_links=False, pre_process=None, via_console=False, from_data_import="No",
	skip_errors = True, data_import_doc=None, validate_template=False, user=None):
	"""upload data"""

	# for translations
	if user:
		frappe.cache().hdel("lang", user)
		frappe.set_user_lang(user)

	if data_import_doc and isinstance(data_import_doc, string_types):
		data_import_doc = frappe.get_doc("Data Import Legacy", data_import_doc)
	if data_import_doc and from_data_import == "Yes":
		no_email = data_import_doc.no_email
		ignore_encoding_errors = data_import_doc.ignore_encoding_errors
		update_only = data_import_doc.only_update
		submit_after_import = data_import_doc.submit_after_import
		overwrite = data_import_doc.overwrite
		skip_errors = data_import_doc.skip_errors
	else:
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
		if not params.get('skip_errors'):
			skip_errors = params.get('skip_errors')

	frappe.flags.in_import = True
	frappe.flags.mute_emails = no_email

	def get_data_keys_definition():
		return get_data_keys()

	def bad_template():
		frappe.throw(_("Please do not change the rows above {0}").format(get_data_keys_definition().data_separator))

	def check_data_length():
		if not data:
			frappe.throw(_("No data found in the file. Please reattach the new file with data."))

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
				if d and doctype_row[i] in (None, '' ,'~', '-', _("DocType") + ":"):
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
			attachments = []
			last_error_row_idx = None
			for idx in range(start_idx, len(rows)):
				last_error_row_idx = idx	# pylint: disable=W0612
				if (not doc) or main_doc_empty(rows[idx]):
					for dt, parentfield in doctypes:
						d = {}
						for column_idx in column_idx_to_fieldname[(dt, parentfield)]:
							try:
								fieldname = column_idx_to_fieldname[(dt, parentfield)][column_idx]
								fieldtype = column_idx_to_fieldtype[(dt, parentfield)][column_idx]

								if not fieldname or not rows[idx][column_idx]:
									continue

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
								elif fieldtype == "Duration":
									d[fieldname] = duration_to_seconds(cstr(d[fieldname]))
								elif fieldtype in ("Image", "Attach Image", "Attach"):
									# added file to attachments list
									attachments.append(d[fieldname])

								elif fieldtype in ("Link", "Dynamic Link", "Data") and d[fieldname]:
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
								if not overwrite and doc.get("name"):
									d['parent'] = doc["name"]
								d['parenttype'] = doctype
								d['parentfield'] = parentfield
								doc.setdefault(d['parentfield'], []).append(d)
				else:
					break

			return doc, attachments, last_error_row_idx
		else:
			doc = frappe._dict(zip(columns, rows[start_idx][1:]))
			doc['doctype'] = doctype
			return doc, [], None

	# used in testing whether a row is empty or parent row or child row
	# checked only 3 first columns since first two columns can be blank for example the case of
	# importing the item variant where item code and item name will be blank.
	def main_doc_empty(row):
		if row:
			for i in range(3,0,-1):
				if len(row) > i and row[i]:
					return False
		return True

	def validate_naming(doc):
		autoname = frappe.get_meta(doctype).autoname
		if autoname:
			if autoname[0:5] == 'field':
				autoname = autoname[6:]
			elif autoname == 'naming_series:':
				autoname = 'naming_series'
			else:
				return True

			if (autoname not in doc) or (not doc[autoname]):
				from frappe.model.base_document import get_controller
				if not hasattr(get_controller(doctype), "autoname"):
					frappe.throw(_("{0} is a mandatory field").format(autoname))
		return True

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

		_file = frappe.get_doc({
			"doctype": "File",
			"file_url": file_url,
			"attached_to_name": docname,
			"attached_to_doctype": doctype,
			"attached_to_field": 0,
			"folder": "Home/Attachments"})
		_file.save()


	# header
	filename, file_extension = ['','']
	if not rows:
		_file = frappe.get_doc("File", {"file_url": data_import_doc.import_file})
		fcontent = _file.get_content()
		filename, file_extension = _file.get_extension()

		if file_extension == '.xlsx' and from_data_import == 'Yes':
			from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
			rows = read_xlsx_file_from_attached_file(file_url=data_import_doc.import_file)

		elif file_extension == '.csv':
			from frappe.utils.csvutils import read_csv_content
			rows = read_csv_content(fcontent, ignore_encoding_errors)

		else:
			frappe.throw(_("Unsupported File Format"))

	start_row = get_start_row()
	header = rows[:start_row]
	data = rows[start_row:]
	try:
		doctype = get_header_row(get_data_keys_definition().main_table)[1]
		columns = filter_empty_columns(get_header_row(get_data_keys_definition().columns)[1:])
	except:
		frappe.throw(_("Cannot change header content"))
	doctypes = []
	column_idx_to_fieldname = {}
	column_idx_to_fieldtype = {}

	if skip_errors:
		data_rows_with_error = header

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

	# Throw expception in case of the empty data file
	check_data_length()
	make_column_map()
	total = len(data)

	if validate_template:
		if total:
			data_import_doc.total_rows = total
		return True

	if overwrite==None:
		overwrite = params.get('overwrite')

	# delete child rows (if parenttype)
	parentfield = None
	if parenttype:
		parentfield = get_parent_field(doctype, parenttype)

		if overwrite:
			delete_child_rows(data, doctype)

	import_log = []
	def log(**kwargs):
		if via_console:
			print((kwargs.get("title") + kwargs.get("message")).encode('utf-8'))
		else:
			import_log.append(kwargs)

	def as_link(doctype, name):
		if via_console:
			return "{0}: {1}".format(doctype, name)
		else:
			return getlink(doctype, name)

	# publish realtime task update
	def publish_progress(achieved, reload=False):
		if data_import_doc:
			frappe.publish_realtime("data_import_progress", {"progress": str(int(100.0*achieved/total)),
				"data_import": data_import_doc.name, "reload": reload}, user=frappe.session.user)


	error_flag = rollback_flag = False

	batch_size = frappe.conf.data_import_batch_size or 1000

	for batch_start in range(0, total, batch_size):
		batch = data[batch_start:batch_start + batch_size]

		for i, row in enumerate(batch):
			# bypass empty rows
			if main_doc_empty(row):
				continue

			row_idx = i + start_row
			doc = None

			publish_progress(i)

			try:
				doc, attachments, last_error_row_idx = get_doc(row_idx)
				validate_naming(doc)
				if pre_process:
					pre_process(doc)

				original = None
				if parentfield:
					parent = frappe.get_doc(parenttype, doc["parent"])
					doc = parent.append(parentfield, doc)
					parent.save()
				else:
					if overwrite and doc.get("name") and frappe.db.exists(doctype, doc["name"]):
						original = frappe.get_doc(doctype, doc["name"])
						original_name = original.name
						original.update(doc)
						# preserve original name for case sensitivity
						original.name = original_name
						original.flags.ignore_links = ignore_links
						original.save()
						doc = original
					else:
						if not update_only:
							doc = frappe.get_doc(doc)
							prepare_for_insert(doc)
							doc.flags.ignore_links = ignore_links
							doc.insert()
					if attachments:
						# check file url and create a File document
						for file_url in attachments:
							attach_file_to_doc(doc.doctype, doc.name, file_url)
					if submit_after_import:
						doc.submit()

				# log errors
				if parentfield:
					log(**{"row": doc.idx, "title": 'Inserted row for "%s"' % (as_link(parenttype, doc.parent)),
						"link": get_absolute_url(parenttype, doc.parent), "message": 'Document successfully saved', "indicator": "green"})
				elif submit_after_import:
					log(**{"row": row_idx + 1, "title":'Submitted row for "%s"' % (as_link(doc.doctype, doc.name)),
						"message": "Document successfully submitted", "link": get_absolute_url(doc.doctype, doc.name), "indicator": "blue"})
				elif original:
					log(**{"row": row_idx + 1,"title":'Updated row for "%s"' % (as_link(doc.doctype, doc.name)),
						"message": "Document successfully updated", "link": get_absolute_url(doc.doctype, doc.name), "indicator": "green"})
				elif not update_only:
					log(**{"row": row_idx + 1, "title":'Inserted row for "%s"' % (as_link(doc.doctype, doc.name)),
						"message": "Document successfully saved", "link": get_absolute_url(doc.doctype, doc.name), "indicator": "green"})
				else:
					log(**{"row": row_idx + 1, "title":'Ignored row for %s' % (row[1]), "link": None,
						"message": "Document updation ignored", "indicator": "orange"})

			except Exception as e:
				error_flag = True

				# build error message
				if frappe.local.message_log:
					err_msg = "\n".join(['<p class="border-bottom small">{}</p>'.format(json.loads(msg).get('message')) for msg in frappe.local.message_log])
				else:
					err_msg = '<p class="border-bottom small">{}</p>'.format(cstr(e))

				error_trace = frappe.get_traceback()
				if error_trace:
					error_log_doc = frappe.log_error(error_trace)
					error_link = get_absolute_url("Error Log", error_log_doc.name)
				else:
					error_link = None

				log(**{
					"row": row_idx + 1,
					"title": 'Error for row %s' % (len(row)>1 and frappe.safe_decode(row[1]) or ""),
					"message": err_msg,
					"indicator": "red",
					"link":error_link
				})

				# data with error to create a new file
				# include the errored data in the last row as last_error_row_idx will not be updated for the last row
				if skip_errors:
					if last_error_row_idx == len(rows)-1:
						last_error_row_idx = len(rows)
					data_rows_with_error += rows[row_idx:last_error_row_idx]
				else:
					rollback_flag = True
			finally:
				frappe.local.message_log = []

		start_row += batch_size
		if rollback_flag:
			frappe.db.rollback()
		else:
			frappe.db.commit()

	frappe.flags.mute_emails = False
	frappe.flags.in_import = False

	log_message = {"messages": import_log, "error": error_flag}
	if data_import_doc:
		data_import_doc.log_details = json.dumps(log_message)

		import_status = None
		if error_flag and data_import_doc.skip_errors and len(data) != len(data_rows_with_error):
			import_status = "Partially Successful"
			# write the file with the faulty row
			file_name = 'error_' + filename + file_extension
			if file_extension == '.xlsx':
				from frappe.utils.xlsxutils import make_xlsx
				xlsx_file = make_xlsx(data_rows_with_error, "Data Import Template")
				file_data = xlsx_file.getvalue()
			else:
				from frappe.utils.csvutils import to_csv
				file_data = to_csv(data_rows_with_error)
			_file = frappe.get_doc({
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": "Data Import Legacy",
				"attached_to_name": data_import_doc.name,
				"folder": "Home/Attachments",
				"content": file_data})
			_file.save()
			data_import_doc.error_file = _file.file_url

		elif error_flag:
			import_status = "Failed"
		else:
			import_status = "Successful"

		data_import_doc.import_status = import_status
		data_import_doc.save()
		if data_import_doc.import_status in ["Successful", "Partially Successful"]:
			data_import_doc.submit()
			publish_progress(100, True)
		else:
			publish_progress(0, True)
		frappe.db.commit()
	else:
		return log_message

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
