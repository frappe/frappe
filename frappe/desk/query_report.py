# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import os, json

from frappe import _
from frappe.modules import scrub, get_module_path
from frappe.utils import flt, cint, get_html_format, get_url_to_form
from frappe.model.utils import render_include
from frappe.translate import send_translations
import frappe.desk.reportview
from frappe.permissions import get_role_permissions
from six import string_types, iteritems
from datetime import timedelta
from frappe.utils import gzip_decompress
from frappe.core.utils import ljust_list

def get_report_doc(report_name):
	doc = frappe.get_doc("Report", report_name)
	doc.custom_columns = []

	if doc.report_type == 'Custom Report':
		custom_report_doc = doc
		reference_report = custom_report_doc.reference_report
		doc = frappe.get_doc("Report", reference_report)
		doc.custom_report = report_name
		doc.custom_columns = custom_report_doc.json
		doc.is_custom_report = True

	if not doc.is_permitted():
		frappe.throw(_("You don't have access to Report: {0}").format(report_name), frappe.PermissionError)

	if not frappe.has_permission(doc.ref_doctype, "report"):
		frappe.throw(_("You don't have permission to get a report on: {0}").format(doc.ref_doctype),
			frappe.PermissionError)

	if doc.disabled:
		frappe.throw(_("Report {0} is disabled").format(report_name))

	return doc


def generate_report_result(report, filters=None, user=None, custom_columns=None):
	user = user or frappe.session.user
	filters = filters or []

	if filters and isinstance(filters, string_types):
		filters = json.loads(filters)

	res = []

	if report.report_type == "Query Report":
		res = report.execute_query_report(filters)

	elif report.report_type == 'Script Report':
		res = report.execute_script_report(filters)

	columns, result, message, chart, data_to_be_printed, skip_total_row = \
		ljust_list(res, 6)

	if report.custom_columns:
		# Original query columns, needed to reorder data as per custom columns
		query_columns = columns
		# Reordered columns
		columns = json.loads(report.custom_columns)

		if report.report_type == 'Query Report':
			result = reorder_data_for_custom_columns(columns, query_columns, result)

		result = add_data_to_custom_columns(columns, result)

	if custom_columns:
		result = add_data_to_custom_columns(custom_columns, result)

		for custom_column in custom_columns:
			columns.insert(custom_column['insert_after_index'] + 1, custom_column)

	if result:
		result = get_filtered_data(report.ref_doctype, columns, result, user)

	if cint(report.add_total_row) and result and not skip_total_row:
		result = add_total_row(result, columns)

	return {
		"result": result,
		"columns": columns,
		"message": message,
		"chart": chart,
		"data_to_be_printed": data_to_be_printed,
		"skip_total_row": skip_total_row or 0,
		"status": None,
		"execution_time": frappe.cache().hget('report_execution_time', report.name) or 0
	}

@frappe.whitelist()
def background_enqueue_run(report_name, filters=None, user=None):
	"""run reports in background"""
	if not user:
		user = frappe.session.user
	report = get_report_doc(report_name)
	track_instance = \
		frappe.get_doc({
			"doctype": "Prepared Report",
			"report_name": report_name,
			# This looks like an insanity but, without this it'd be very hard to find Prepared Reports matching given condition
			# We're ensuring that spacing is consistent. e.g. JS seems to put no spaces after ":", Python on the other hand does.
			"filters": json.dumps(json.loads(filters)),
			"ref_report_doctype": report_name,
			"report_type": report.report_type,
			"query": report.query,
			"module": report.module,
		})
	track_instance.insert(ignore_permissions=True)
	frappe.db.commit()
	track_instance.enqueue_report()

	return {
		"name": track_instance.name,
		"redirect_url": get_url_to_form("Prepared Report", track_instance.name)
	}


@frappe.whitelist()
def get_script(report_name):
	report = get_report_doc(report_name)
	module = report.module or frappe.db.get_value("DocType", report.ref_doctype, "module")
	module_path = get_module_path(module)
	report_folder = os.path.join(module_path, "report", scrub(report.name))
	script_path = os.path.join(report_folder, scrub(report.name) + ".js")
	print_path = os.path.join(report_folder, scrub(report.name) + ".html")

	script = None
	if os.path.exists(script_path):
		with open(script_path, "r") as f:
			script = f.read()

	html_format = get_html_format(print_path)

	if not script and report.javascript:
		script = report.javascript

	if not script:
		script = "frappe.query_reports['%s']={}" % report_name

	# load translations
	if frappe.lang != "en":
		send_translations(frappe.get_lang_dict("report", report_name))

	return {
		"script": render_include(script),
		"html_format": html_format,
		"execution_time": frappe.cache().hget('report_execution_time', report_name) or 0
	}


@frappe.whitelist()
@frappe.read_only()
def run(report_name, filters=None, user=None, ignore_prepared_report=False, custom_columns=None):

	report = get_report_doc(report_name)
	if not user:
		user = frappe.session.user
	if not frappe.has_permission(report.ref_doctype, "report"):
		frappe.msgprint(_("Must have report permission to access this report."),
			raise_exception=True)

	result = None

	if report.prepared_report and not report.disable_prepared_report and not ignore_prepared_report:
		if filters:
			if isinstance(filters, string_types):
				filters = json.loads(filters)

			dn = filters.get("prepared_report_name")
			filters.pop("prepared_report_name", None)
		else:
			dn = ""
		result = get_prepared_report_result(report, filters, dn, user)
	else:
		result = generate_report_result(report, filters, user, custom_columns)

	result["add_total_row"] = report.add_total_row and not result.get('skip_total_row', False)

	return result

def add_data_to_custom_columns(columns, result):
	custom_fields_data = get_data_for_custom_report(columns)

	data = []
	for row in result:
		row_obj = {}
		if isinstance(row, tuple):
			row = list(row)

		if isinstance(row, list):
			for idx, column in enumerate(columns):
				if column.get('link_field'):
					row_obj[column['fieldname']] = None
					row.insert(idx, None)
				else:
					row_obj[column['fieldname']] = row[idx]
			data.append(row_obj)
		else:
			data.append(row)

	for row in data:
		for column in columns:
			if column.get('link_field'):
				fieldname = column['fieldname']
				key = (column['doctype'], fieldname)
				link_field = column['link_field']
				row[fieldname] = custom_fields_data.get(key, {}).get(row.get(link_field))

	return data

def reorder_data_for_custom_columns(custom_columns, columns, result):
	reordered_result = []
	columns = [col.split(":")[0] for col in columns]

	for res in result:
		r = []
		for col in custom_columns:
			try:
				idx = columns.index(col.get("label"))
				r.append(res[idx])
			except ValueError:
				pass

		reordered_result.append(r)

	return reordered_result

def get_prepared_report_result(report, filters, dn="", user=None):
	latest_report_data = {}
	doc = None
	if dn:
		# Get specified dn
		doc = frappe.get_doc("Prepared Report", dn)
	else:
		# Only look for completed prepared reports with given filters.
		doc_list = frappe.get_all("Prepared Report",
			filters={
				"status": "Completed",
				"filters": json.dumps(filters),
				"owner": user,
				"report_name": report.get('custom_report') or report.get('report_name')
			},
			order_by = 'creation desc'
		)

		if doc_list:
			# Get latest
			doc = frappe.get_doc("Prepared Report", doc_list[0])

	if doc:
		try:
			# Prepared Report data is stored in a GZip compressed JSON file
			attached_file_name = frappe.db.get_value("File", {"attached_to_doctype": doc.doctype, "attached_to_name":doc.name}, "name")
			attached_file = frappe.get_doc('File', attached_file_name)
			compressed_content = attached_file.get_content()
			uncompressed_content = gzip_decompress(compressed_content)
			data = json.loads(uncompressed_content)
			if data:
				columns = json.loads(doc.columns) if doc.columns else data[0]

				for column in columns:
					if isinstance(column, dict) and column.get("label"):
						column["label"] = _(column["label"])

				latest_report_data = {
					"columns": columns,
					"result": data
				}
		except Exception:
			frappe.log_error(frappe.get_traceback())
			frappe.delete_doc("Prepared Report", doc.name)
			frappe.db.commit()
			doc = None

	latest_report_data.update({
		"prepared_report": True,
		"doc": doc
	})

	return latest_report_data

@frappe.whitelist()
def export_query():
	"""export from query reports"""

	data = frappe._dict(frappe.local.form_dict)

	del data["cmd"]
	if "csrf_token" in data:
		del data["csrf_token"]

	if isinstance(data.get("filters"), string_types):
		filters = json.loads(data["filters"])
	if isinstance(data.get("report_name"), string_types):
		report_name = data["report_name"]
		frappe.permissions.can_export(
			frappe.get_cached_value('Report', report_name, 'ref_doctype'),
			raise_exception=True
		)
	if isinstance(data.get("file_format_type"), string_types):
		file_format_type = data["file_format_type"]

	custom_columns = frappe.parse_json(data["custom_columns"])

	include_indentation = data["include_indentation"]
	if isinstance(data.get("visible_idx"), string_types):
		visible_idx = json.loads(data.get("visible_idx"))
	else:
		visible_idx = None

	if file_format_type == "Excel":
		data = run(report_name, filters, custom_columns=custom_columns)
		data = frappe._dict(data)
		if not data.columns:
			frappe.respond_as_web_page(_("No data to export"),
			_("You can try changing the filters of your report."))
			return

		columns = get_columns_dict(data.columns)

		from frappe.utils.xlsxutils import make_xlsx
		xlsx_data = build_xlsx_data(columns, data, visible_idx, include_indentation)
		xlsx_file = make_xlsx(xlsx_data, "Query Report")

		frappe.response['filename'] = report_name + '.xlsx'
		frappe.response['filecontent'] = xlsx_file.getvalue()
		frappe.response['type'] = 'binary'


def build_xlsx_data(columns, data, visible_idx, include_indentation):
	result = [[]]

	# add column headings
	for idx in range(len(data.columns)):
		if not columns[idx].get("hidden"):
			result[0].append(columns[idx]["label"])

	# build table from result
	for i, row in enumerate(data.result):
		# only pick up rows that are visible in the report
		if i in visible_idx:
			row_data = []

			if isinstance(row, dict) and row:
				for idx in range(len(data.columns)):
					if not columns[idx].get("hidden"):
						label = columns[idx]["label"]
						fieldname = columns[idx]["fieldname"]
						cell_value = row.get(fieldname, row.get(label, ""))
						if cint(include_indentation) and 'indent' in row and idx == 0:
							cell_value = ('    ' * cint(row['indent'])) + cell_value
						row_data.append(cell_value)
			else:
				row_data = row

			result.append(row_data)

	return result

def add_total_row(result, columns, meta = None):
	total_row = [""]*len(columns)
	has_percent = []
	for i, col in enumerate(columns):
		fieldtype, options, fieldname = None, None, None
		if isinstance(col, string_types):
			if meta:
				# get fieldtype from the meta
				field = meta.get_field(col)
				if field:
					fieldtype = meta.get_field(col).fieldtype
					fieldname = meta.get_field(col).fieldname
			else:
				col = col.split(":")
				if len(col) > 1:
					if col[1]:
						fieldtype = col[1]
						if "/" in fieldtype:
							fieldtype, options = fieldtype.split("/")
					else:
						fieldtype = "Data"
		else:
			fieldtype = col.get("fieldtype")
			fieldname = col.get("fieldname")
			options = col.get("options")

		for row in result:
			if i >= len(row): continue

			cell = row.get(fieldname) if isinstance(row, dict) else row[i]
			if fieldtype in ["Currency", "Int", "Float", "Percent"] and flt(cell):
				total_row[i] = flt(total_row[i]) + flt(cell)

			if fieldtype == "Percent" and i not in has_percent:
				has_percent.append(i)

			if fieldtype == "Time" and cell:
				if not total_row[i]:
					total_row[i]=timedelta(hours=0,minutes=0,seconds=0)
				total_row[i] =  total_row[i] + cell


		if fieldtype=="Link" and options == "Currency":
			total_row[i] = result[0].get(fieldname) if isinstance(result[0], dict) else result[0][i]

	for i in has_percent:
		total_row[i] = flt(total_row[i]) / len(result)

	first_col_fieldtype = None
	if isinstance(columns[0], string_types):
		first_col = columns[0].split(":")
		if len(first_col) > 1:
			first_col_fieldtype = first_col[1].split("/")[0]
	else:
		first_col_fieldtype = columns[0].get("fieldtype")

	if first_col_fieldtype not in ["Currency", "Int", "Float", "Percent", "Date"]:
		total_row[0] = _("Total")

	result.append(total_row)
	return result

@frappe.whitelist()
def get_data_for_custom_field(doctype, field):

	value_map = frappe._dict(frappe.get_all(doctype,
		fields=["name", field],
		as_list=1))

	return value_map

def get_data_for_custom_report(columns):
	doc_field_value_map = {}

	for column in columns:
		if column.get('link_field'):
			fieldname = column.get('fieldname')
			doctype = column.get('doctype')
			doc_field_value_map[(doctype, fieldname)] = get_data_for_custom_field(doctype, fieldname)

	return doc_field_value_map

@frappe.whitelist()
def save_report(reference_report, report_name, columns):
	report_doc = get_report_doc(reference_report)

	docname = frappe.db.exists("Report", report_name)
	if docname:
		report = frappe.get_doc("Report", {'report_name': docname, 'is_standard': 'No', 'report_type': 'Custom Report'})
		report.update({"json": columns})
		report.save()
		frappe.msgprint(_("Report updated successfully"))

		return docname
	else:
		new_report = frappe.get_doc({
			'doctype': 'Report',
			'report_name': report_name,
			'json': columns,
			'ref_doctype': report_doc.ref_doctype,
			'is_standard': 'No',
			'report_type': 'Custom Report',
			'reference_report': reference_report
		}).insert(ignore_permissions = True)
		frappe.msgprint(_("{0} saved successfully".format(new_report.name)))
		return new_report.name


def get_filtered_data(ref_doctype, columns, data, user):
	result = []
	linked_doctypes = get_linked_doctypes(columns, data)
	match_filters_per_doctype = get_user_match_filters(linked_doctypes, user=user)
	shared = frappe.share.get_shared(ref_doctype, user)
	columns_dict = get_columns_dict(columns)

	role_permissions = get_role_permissions(frappe.get_meta(ref_doctype), user)
	if_owner = role_permissions.get("if_owner", {}).get("report")

	if match_filters_per_doctype:
		for row in data:
			# Why linked_doctypes.get(ref_doctype)? because if column is empty, linked_doctypes[ref_doctype] is removed
			if linked_doctypes.get(ref_doctype) and shared and row[linked_doctypes[ref_doctype]] in shared:
				result.append(row)

			elif has_match(row, linked_doctypes, match_filters_per_doctype, ref_doctype, if_owner, columns_dict, user):
				result.append(row)
	else:
		result = list(data)

	return result


def has_match(row, linked_doctypes, doctype_match_filters, ref_doctype, if_owner, columns_dict, user):
	"""Returns True if after evaluating permissions for each linked doctype
		- There is an owner match for the ref_doctype
		- `and` There is a user permission match for all linked doctypes

		Returns True if the row is empty

		Note:
		Each doctype could have multiple conflicting user permission doctypes.
		Hence even if one of the sets allows a match, it is true.
		This behavior is equivalent to the trickling of user permissions of linked doctypes to the ref doctype.
	"""
	resultant_match = True

	if not row:
		# allow empty rows :)
		return resultant_match

	for doctype, filter_list in doctype_match_filters.items():
		matched_for_doctype = False

		if doctype==ref_doctype and if_owner:
			idx = linked_doctypes.get("User")
			if (idx is not None
				and row[idx]==user
				and columns_dict[idx]==columns_dict.get("owner")):
					# owner match is true
					matched_for_doctype = True

		if not matched_for_doctype:
			for match_filters in filter_list:
				match = True
				for dt, idx in linked_doctypes.items():
					# case handled above
					if dt=="User" and columns_dict[idx]==columns_dict.get("owner"):
						continue

					cell_value = None
					if isinstance(row, dict):
						cell_value = row.get(idx)
					elif isinstance(row, (list, tuple)):
						cell_value = row[idx]

					if dt in match_filters and cell_value not in match_filters.get(dt) and frappe.db.exists(dt, cell_value):
						match = False
						break

				# each doctype could have multiple conflicting user permission doctypes, hence using OR
				# so that even if one of the sets allows a match, it is true
				matched_for_doctype = matched_for_doctype or match

				if matched_for_doctype:
					break

		# each doctype's user permissions should match the row! hence using AND
		resultant_match = resultant_match and matched_for_doctype

		if not resultant_match:
			break

	return resultant_match

def get_linked_doctypes(columns, data):
	linked_doctypes = {}

	columns_dict = get_columns_dict(columns)

	for idx, col in enumerate(columns):
		df = columns_dict[idx]
		if df.get("fieldtype")=="Link":
			if data and isinstance(data[0], (list, tuple)):
				linked_doctypes[df["options"]] = idx
			else:
				# dict
				linked_doctypes[df["options"]] = df["fieldname"]

	# remove doctype if column is empty
	columns_with_value = []
	for row in data:
		if row:
			if len(row) != len(columns_with_value):
				if isinstance(row, (list, tuple)):
					row = enumerate(row)
				elif isinstance(row, dict):
					row = row.items()

				for col, val in row:
					if val and col not in columns_with_value:
						columns_with_value.append(col)

	items = list(iteritems(linked_doctypes))

	for doctype, key in items:
		if key not in columns_with_value:
			del linked_doctypes[doctype]

	return linked_doctypes

def get_columns_dict(columns):
	"""Returns a dict with column docfield values as dict
		The keys for the dict are both idx and fieldname,
		so either index or fieldname can be used to search for a column's docfield properties
	"""
	columns_dict = frappe._dict()
	for idx, col in enumerate(columns):
		col_dict = frappe._dict()

		# string
		if isinstance(col, string_types):
			col = col.split(":")
			if len(col) > 1:
				if "/" in col[1]:
					col_dict["fieldtype"], col_dict["options"] = col[1].split("/")
				else:
					col_dict["fieldtype"] = col[1]

			col_dict["label"] = col[0]
			col_dict["fieldname"] = frappe.scrub(col[0])

		# dict
		else:
			col_dict.update(col)
			if "fieldname" not in col_dict:
				col_dict["fieldname"] = frappe.scrub(col_dict["label"])

		columns_dict[idx] = col_dict
		columns_dict[col_dict["fieldname"]] = col_dict

	return columns_dict

def get_user_match_filters(doctypes, user):
	match_filters = {}

	for dt in doctypes:
		filter_list = frappe.desk.reportview.build_match_conditions(dt, user, False)
		if filter_list:
			match_filters[dt] = filter_list

	return match_filters
