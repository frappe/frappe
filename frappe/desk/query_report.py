# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime
import json
import os
from datetime import timedelta

import frappe
import frappe.desk.reportview
from frappe import _
from frappe.core.utils import ljust_list
from frappe.desk.reportview import clean_params, parse_json
from frappe.model.utils import render_include
from frappe.modules import get_module_path, scrub
from frappe.monitor import add_data_to_monitor
from frappe.permissions import get_role_permissions, get_roles, has_permission
from frappe.utils import cint, cstr, flt, format_duration, get_html_format, sbool
from frappe.utils.caching import request_cache


def get_report_doc(report_name):
	doc = frappe.get_doc("Report", report_name)
	doc.custom_columns = []
	doc.custom_filters = []

	if doc.report_type == "Custom Report":
		custom_report_doc = doc
		doc = get_reference_report(doc)
		doc.custom_report = report_name
		if custom_report_doc.json:
			data = json.loads(custom_report_doc.json)
			if data:
				doc.custom_columns = data.get("columns")
				doc.custom_filters = data.get("filters")
		doc.is_custom_report = True

		# Follow whatever the custom report has set for prepared report field
		doc.prepared_report = custom_report_doc.prepared_report

	if not doc.is_permitted():
		frappe.throw(
			_("You don't have access to Report: {0}").format(_(doc.name)),
			frappe.PermissionError,
		)

	if not frappe.has_permission(doc.ref_doctype, "report"):
		frappe.throw(
			_("You don't have permission to get a report on: {0}").format(_(doc.ref_doctype)),
			frappe.PermissionError,
		)

	if doc.disabled:
		frappe.throw(_("Report {0} is disabled").format(_(report_name)))

	return doc


def get_report_result(report, filters):
	res = None

	if report.report_type == "Query Report":
		res = report.execute_query_report(filters)

	elif report.report_type == "Script Report":
		res = report.execute_script_report(filters)

	elif report.report_type == "Custom Report":
		ref_report = get_report_doc(report.report_name)
		res = get_report_result(ref_report, filters)

	return res


@frappe.read_only()
def generate_report_result(
	report, filters=None, user=None, custom_columns=None, is_tree=False, parent_field=None
):
	user = user or frappe.session.user
	filters = filters or []

	if filters and isinstance(filters, str):
		filters = json.loads(filters)

	res = get_report_result(report, filters) or []

	columns, result, message, chart, report_summary, skip_total_row = ljust_list(res, 6)
	columns = [get_column_as_dict(col) for col in (columns or [])]
	report_column_names = [col["fieldname"] for col in columns]
	# convert to list of dicts

	result = normalize_result(result, columns)

	if report.get("custom_columns"):
		# saved columns (with custom columns / with different column order)
		columns = report.custom_columns

	# unsaved custom_columns
	if custom_columns:
		for custom_column in custom_columns:
			columns.insert(custom_column["insert_after_index"] + 1, custom_column)

	# all columns which are not in original report
	report_custom_columns = [column for column in columns if column["fieldname"] not in report_column_names]

	if report_custom_columns:
		result = add_custom_column_data(report_custom_columns, result)

	if result:
		result = get_filtered_data(report.ref_doctype, columns, result, user)

	if cint(report.add_total_row) and result and not skip_total_row:
		result = add_total_row(result, columns, is_tree=is_tree, parent_field=parent_field)

	if isinstance(filters, dict) and filters.get("translate_data"):
		total_row = cint(report.add_total_row) and result and not skip_total_row
		result = translate_report_data(result, total_row)

	return {
		"result": result,
		"columns": columns,
		"message": message,
		"chart": chart,
		"report_summary": report_summary,
		"skip_total_row": skip_total_row or 0,
		"status": None,
		"execution_time": frappe.cache.hget("report_execution_time", report.name) or 0,
	}


def normalize_result(result, columns):
	# Convert to list of dicts from list of lists/tuples
	data = []
	column_names = [column["fieldname"] for column in columns]
	if result and isinstance(result[0], list | tuple):
		for row in result:
			row_obj = {}
			for idx, column_name in enumerate(column_names):
				row_obj[column_name] = row[idx]
			data.append(row_obj)
	else:
		data = result

	return data


@frappe.whitelist()
def get_script(report_name):
	report = get_report_doc(report_name)
	module = report.module or frappe.db.get_value("DocType", report.ref_doctype, "module")

	is_custom_module = frappe.get_cached_value("Module Def", module, "custom")

	# custom modules are virtual modules those exists in DB but not in disk.
	module_path = "" if is_custom_module else get_module_path(module)
	report_folder = module_path and os.path.join(module_path, "report", scrub(report.name))
	script_path = report_folder and os.path.join(report_folder, scrub(report.name) + ".js")
	print_path = report_folder and os.path.join(report_folder, scrub(report.name) + ".html")

	script = None
	if os.path.exists(script_path):
		with open(script_path) as f:
			script = f.read()
			script += f"\n\n//# sourceURL={scrub(report.name)}.js"

	html_format = get_html_format(print_path)

	if not script and report.javascript:
		script = report.javascript
		script += f"\n\n//# sourceURL={scrub(report.name)}__custom"

	if not script:
		script = "frappe.query_reports['{}']={{}}".format(report_name)

	return {
		"script": render_include(script),
		"html_format": html_format,
		"execution_time": frappe.cache.hget("report_execution_time", report_name) or 0,
		"filters": report.filters,
		"custom_report_name": report.name if report.get("is_custom_report") else None,
	}


def get_reference_report(report):
	if report.report_type != "Custom Report":
		return report
	reference_report = frappe.get_doc("Report", report.reference_report)
	return get_reference_report(reference_report)


@frappe.whitelist()
@frappe.read_only()
def run(
	report_name,
	filters=None,
	user=None,
	ignore_prepared_report=False,
	custom_columns=None,
	is_tree=False,
	parent_field=None,
	are_default_filters=True,
):
	if not user:
		user = frappe.session.user
	validate_filters_permissions(report_name, filters, user)
	report = get_report_doc(report_name)
	if not frappe.has_permission(report.ref_doctype, "report"):
		frappe.msgprint(
			_("Must have report permission to access this report."),
			raise_exception=True,
		)

	result = None

	if sbool(are_default_filters) and report.get("custom_filters"):
		filters = report.custom_filters

	try:
		if report.prepared_report and not sbool(ignore_prepared_report) and not custom_columns:
			if filters:
				if isinstance(filters, str):
					filters = json.loads(filters)

				dn = filters.pop("prepared_report_name", None)
			else:
				dn = ""
			result = get_prepared_report_result(report, filters, dn, user)
		else:
			result = generate_report_result(report, filters, user, custom_columns, is_tree, parent_field)
			add_data_to_monitor(report=report.reference_report or report.name)
	except Exception:
		frappe.log_error("Report Error")
		raise

	result["add_total_row"] = report.add_total_row and not result.get("skip_total_row", False)

	if sbool(are_default_filters) and report.get("custom_filters"):
		result["custom_filters"] = report.custom_filters

	return result


def add_custom_column_data(custom_columns, result):
	doctype_names_from_custom_field = []
	for column in custom_columns:
		if len(column["fieldname"].split("-")) > 1:
			# length greater than 1, means that the column is a custom field with confilicting fieldname
			doctype_name = frappe.unscrub(column["fieldname"].split("-")[1])
			doctype_names_from_custom_field.append(doctype_name)
		column["fieldname"] = column["fieldname"].split("-")[0]

	custom_column_data = get_data_for_custom_report(custom_columns, result)

	for column in custom_columns:
		key = (column.get("doctype"), column.get("fieldname"))
		if key in custom_column_data:
			for row in result:
				link_field = column.get("link_field")

				# backwards compatibile `link_field`
				# old custom reports which use `str` should not break.
				if isinstance(link_field, str):
					link_field = frappe._dict({"fieldname": link_field, "names": []})

				row_reference = row.get(link_field.get("fieldname"))
				# possible if the row is empty
				if not row_reference:
					continue
				if key[0] in doctype_names_from_custom_field:
					column["fieldname"] = column.get("id")
				row[column.get("fieldname")] = custom_column_data.get(key).get(row_reference)

	return result


def get_prepared_report_result(report, filters, dn="", user=None):
	from frappe.core.doctype.prepared_report.prepared_report import get_completed_prepared_report

	def get_report_data(doc, data):
		# backwards compatibility - prepared report used to have a columns field,
		# we now directly fetch it from the result file
		if doc.get("columns") or isinstance(data, list):
			columns = (doc.get("columns") and json.loads(doc.columns)) or data[0]
			data = {"result": data}
		else:
			columns = data.get("columns")

		for column in columns:
			if isinstance(column, dict) and column.get("label"):
				column["label"] = _(column["label"])

		return data | {"columns": columns}

	report_data = {}
	if not dn:
		dn = get_completed_prepared_report(
			filters, user, report.get("custom_report") or report.get("report_name")
		)

	doc = frappe.get_doc("Prepared Report", dn) if dn else None
	if doc:
		try:
			if data := json.loads(doc.get_prepared_data().decode("utf-8")):
				report_data = get_report_data(doc, data)
		except Exception as e:
			doc.log_error("Prepared report render failed")
			frappe.msgprint(_("Prepared report render failed") + f": {e!s}")
			doc = None

	return report_data | {"prepared_report": True, "doc": doc}


@frappe.whitelist()
def export_query():
	"""export from query reports"""
	from frappe.desk.utils import get_csv_bytes, pop_csv_params, provide_binary_file

	form_params = frappe._dict(frappe.local.form_dict)
	csv_params = pop_csv_params(form_params)
	clean_params(form_params)
	parse_json(form_params)
	report_name = form_params.report_name
	frappe.permissions.can_export(
		frappe.get_cached_value("Report", report_name, "ref_doctype"),
		raise_exception=True,
	)

	file_format_type = form_params.file_format_type
	custom_columns = frappe.parse_json(form_params.custom_columns or "[]")
	include_indentation = form_params.include_indentation
	include_filters = form_params.include_filters
	visible_idx = form_params.visible_idx
	include_hidden_columns = form_params.include_hidden_columns

	if isinstance(visible_idx, str):
		visible_idx = json.loads(visible_idx)

	data = run(report_name, form_params.filters, custom_columns=custom_columns, are_default_filters=False)
	data = frappe._dict(data)
	data.filters = form_params.applied_filters

	if not data.columns:
		frappe.respond_as_web_page(
			_("No data to export"),
			_("You can try changing the filters of your report."),
		)
		return

	format_fields(data)
	xlsx_data, column_widths = build_xlsx_data(
		data,
		visible_idx,
		include_indentation,
		include_filters=include_filters,
		include_hidden_columns=include_hidden_columns,
	)

	if file_format_type == "CSV":
		content = get_csv_bytes(xlsx_data, csv_params)
		file_extension = "csv"
	elif file_format_type == "Excel":
		from frappe.utils.xlsxutils import make_xlsx

		file_extension = "xlsx"
		content = make_xlsx(xlsx_data, "Query Report", column_widths=column_widths).getvalue()

	if include_filters:
		for value in (data.filters or {}).values():
			suffix = ""
			if isinstance(value, list):
				suffix = "_" + ",".join(value)
			elif isinstance(value, str) and value not in {"Yes", "No"}:
				suffix = f"_{value}"

			if valid_report_name(report_name, suffix):
				report_name += suffix

	provide_binary_file(report_name, file_extension, content)


def valid_report_name(report_name, suffix):
	if len(report_name) + len(suffix) < 200:
		return True
	return False


def format_fields(data: frappe._dict) -> None:
	for i, col in enumerate(data.columns):
		if col.get("fieldtype") == "Duration":
			for row in data.result:
				index = col.get("fieldname") if isinstance(row, dict) else i
				if row[index]:
					row[index] = format_duration(row[index])
		elif col.get("fieldtype") == "Currency" and col.get("precision"):
			for row in data.result:
				index = col.get("fieldname") if isinstance(row, dict) else i
				if row[index]:
					row[index] = round(row[index], col.get("precision"))


def build_xlsx_data(
	data,
	visible_idx,
	include_indentation,
	include_filters=False,
	ignore_visible_idx=False,
	include_hidden_columns=False,
):
	EXCEL_TYPES = (
		str,
		bool,
		type(None),
		int,
		float,
		datetime.datetime,
		datetime.date,
		datetime.time,
		datetime.timedelta,
	)

	if len(visible_idx) == len(data.result) or not visible_idx:
		# It's not possible to have same length and different content.
		ignore_visible_idx = True
	else:
		# Note: converted for faster lookups
		visible_idx = set(visible_idx)

	result = []
	column_widths = []

	if cint(include_filters):
		filter_data = []
		filters = data.filters
		for filter_name, filter_value in filters.items():
			if not filter_value:
				continue
			filter_value = (
				", ".join([cstr(x) for x in filter_value])
				if isinstance(filter_value, list)
				else cstr(filter_value)
			)
			filter_data.append([cstr(filter_name), filter_value])
		filter_data.append([])
		result += filter_data

	column_data = []
	for column in data.columns:
		if column.get("hidden") and not cint(include_hidden_columns):
			continue
		column_data.append(_(column.get("label")))
		column_width = cint(column.get("width", 0))
		# to convert into scale accepted by openpyxl
		column_width /= 10
		column_widths.append(column_width)
	result.append(column_data)

	# build table from result
	for row_idx, row in enumerate(data.result):
		# only pick up rows that are visible in the report
		if ignore_visible_idx or row_idx in visible_idx:
			row_data = []
			if isinstance(row, dict):
				for col_idx, column in enumerate(data.columns):
					if column.get("hidden") and not cint(include_hidden_columns):
						continue
					label = column.get("label")
					fieldname = column.get("fieldname")
					cell_value = row.get(fieldname, row.get(label, ""))
					if not isinstance(cell_value, EXCEL_TYPES):
						cell_value = cstr(cell_value)

					if cint(include_indentation) and "indent" in row and col_idx == 0:
						cell_value = ("    " * cint(row["indent"])) + cstr(cell_value)
					row_data.append(cell_value)
			elif row:
				row_data = row

			result.append(row_data)

	return result, column_widths


def add_total_row(result, columns, meta=None, is_tree=False, parent_field=None):
	total_row = [""] * len(columns)
	has_percent = []

	for i, col in enumerate(columns):
		fieldtype, options, fieldname = None, None, None
		if isinstance(col, str):
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
			if i >= len(row):
				continue
			cell = row.get(fieldname) if isinstance(row, dict) else row[i]
			if fieldtype is None:
				if isinstance(cell, int):
					fieldtype = "Int"
				elif isinstance(cell, float):
					fieldtype = "Float"
			if fieldtype in ["Currency", "Int", "Float", "Percent", "Duration"] and flt(cell):
				if not (is_tree and row.get(parent_field)):
					total_row[i] = flt(total_row[i]) + flt(cell)

			if fieldtype == "Percent" and i not in has_percent:
				has_percent.append(i)

			if fieldtype == "Time" and cell:
				if not total_row[i]:
					total_row[i] = timedelta(hours=0, minutes=0, seconds=0)
				total_row[i] = total_row[i] + cell

		if fieldtype == "Link" and options == "Currency":
			total_row[i] = result[0].get(fieldname) if isinstance(result[0], dict) else result[0][i]

	for i in has_percent:
		total_row[i] = flt(total_row[i]) / len(result)

	first_col_fieldtype = None
	if isinstance(columns[0], str):
		first_col = columns[0].split(":")
		if len(first_col) > 1:
			first_col_fieldtype = first_col[1].split("/", 1)[0]
	else:
		first_col_fieldtype = columns[0].get("fieldtype")

	if first_col_fieldtype not in ["Currency", "Int", "Float", "Percent", "Date"]:
		total_row[0] = _("Total")

	result.append(total_row)
	return result


@frappe.whitelist()
def get_data_for_custom_field(doctype, field, names=None):
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not Permitted to read {0}").format(_(doctype)), frappe.PermissionError)

	filters = {}
	if names:
		if isinstance(names, str | bytearray):
			names = frappe.json.loads(names)
		filters.update({"name": ["in", names]})

	return frappe._dict(frappe.get_list(doctype, filters=filters, fields=["name", field], as_list=1))


def get_data_for_custom_report(columns, result):
	doc_field_value_map = {}

	for column in columns:
		if link_field := column.get("link_field"):
			# backwards compatibile `link_field`
			# old custom reports which use `str` should not break
			if isinstance(link_field, str):
				link_field = frappe._dict({"fieldname": link_field, "names": []})

			fieldname = column.get("fieldname")
			doctype = column.get("doctype")

			row_key = link_field.get("fieldname")
			names = []
			for row in result:
				if row.get(row_key):
					names.append(row.get(row_key))
			names = list(set(names))

			doc_field_value_map[(doctype, fieldname)] = get_data_for_custom_field(doctype, fieldname, names)
	return doc_field_value_map


@frappe.whitelist()
def save_report(reference_report, report_name, columns, filters):
	report_doc = get_report_doc(reference_report)

	docname = frappe.db.exists(
		"Report",
		{
			"report_name": report_name,
			"is_standard": "No",
			"report_type": "Custom Report",
		},
	)

	if docname:
		report = frappe.get_doc("Report", docname)
		existing_jd = json.loads(report.json)
		existing_jd["columns"] = json.loads(columns)
		existing_jd["filters"] = json.loads(filters)
		report.update({"json": json.dumps(existing_jd, separators=(",", ":"))})
		report.save()
		frappe.msgprint(_("Report updated successfully"))

		return docname
	else:
		new_report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": report_name,
				"json": f'{{"columns":{columns},"filters":{filters}}}',
				"ref_doctype": report_doc.ref_doctype,
				"is_standard": "No",
				"report_type": "Custom Report",
				"reference_report": reference_report,
			}
		).insert(ignore_permissions=True)
		frappe.msgprint(_("{0} saved successfully").format(_(new_report.name)))
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
			if (
				linked_doctypes.get(ref_doctype)
				and shared
				and row.get(linked_doctypes[ref_doctype]) in shared
			):
				result.append(row)

			elif has_match(
				row,
				linked_doctypes,
				match_filters_per_doctype,
				ref_doctype,
				if_owner,
				columns_dict,
				user,
			):
				result.append(row)
	else:
		result = list(data)

	return result


def has_match(
	row,
	linked_doctypes,
	doctype_match_filters,
	ref_doctype,
	if_owner,
	columns_dict,
	user,
):
	"""Return True if after evaluating permissions for each linked doctype:
	        - There is an owner match for the ref_doctype
	        - `and` There is a user permission match for all linked doctypes

	Return True if the row is empty.

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

		if doctype == ref_doctype and if_owner:
			idx = linked_doctypes.get("User")
			if idx is not None and row[idx] == user and columns_dict[idx] == columns_dict.get("owner"):
				# owner match is true
				matched_for_doctype = True

		if not matched_for_doctype:
			for match_filters in filter_list:
				match = True
				for dt, idx in linked_doctypes.items():
					# case handled above
					if dt == "User" and columns_dict[idx] == columns_dict.get("owner"):
						continue

					cell_value = None
					if isinstance(row, dict):
						cell_value = row.get(idx)
					elif isinstance(row, list | tuple):
						cell_value = row[idx]

					if (
						dt in match_filters
						and cell_value not in match_filters.get(dt)
						and frappe.db.exists(dt, cell_value)
					):
						match = False
						break

					if match:
						match = has_unrestricted_read_access(doctype=ref_doctype, user=frappe.session.user)

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


@request_cache
def has_unrestricted_read_access(doctype, user):
	roles = get_roles(user)

	permission_filters = {
		"parent": doctype,
		"role": ["in", roles],
		"permlevel": 0,
		"read": 1,
		"if_owner": 0,
	}

	standard_perm_exists = frappe.db.exists(
		"DocPerm",
		permission_filters,
	)

	custom_perm_exists = frappe.db.exists(
		"Custom DocPerm",
		permission_filters,
	)

	has_perm = bool(custom_perm_exists or standard_perm_exists)
	return has_perm


def get_linked_doctypes(columns, data):
	linked_doctypes = {}

	columns_dict = get_columns_dict(columns)

	for idx in range(len(columns)):
		df = columns_dict[idx]
		if df.get("fieldtype") == "Link":
			if data and isinstance(data[0], list | tuple):
				linked_doctypes[df["options"]] = idx
			else:
				# dict
				linked_doctypes[df["options"]] = df["fieldname"]

	# remove doctype if column is empty
	columns_with_value = []
	for row in data:
		if row:
			if len(row) != len(columns_with_value):
				if isinstance(row, list | tuple):
					row = enumerate(row)
				elif isinstance(row, dict):
					row = row.items()

				for col, val in row:
					if val and col not in columns_with_value:
						columns_with_value.append(col)

	items = list(linked_doctypes.items())

	for doctype, key in items:
		if key not in columns_with_value:
			del linked_doctypes[doctype]

	return linked_doctypes


def get_columns_dict(columns):
	"""Return a dict with column docfield values as dict.

	The keys for the dict are both idx and fieldname,
	so either index or fieldname can be used to search for a column's docfield properties.
	"""
	columns_dict = frappe._dict()
	for idx, col in enumerate(columns):
		col_dict = get_column_as_dict(col)
		columns_dict[idx] = col_dict
		columns_dict[col_dict["fieldname"]] = col_dict

	return columns_dict


def get_column_as_dict(col):
	col_dict = frappe._dict()

	# string
	if isinstance(col, str):
		col = col.split(":")
		if len(col) > 1:
			if "/" in col[1]:
				col_dict["fieldtype"], col_dict["options"] = col[1].split("/")
			else:
				col_dict["fieldtype"] = col[1]
			if len(col) == 3:
				col_dict["width"] = col[2]

		col_dict["label"] = col[0]
		col_dict["fieldname"] = frappe.scrub(col[0])

	# dict
	else:
		col_dict.update(col)
		if "fieldname" not in col_dict:
			col_dict["fieldname"] = frappe.scrub(col_dict["label"])

	return col_dict


def get_user_match_filters(doctypes, user):
	match_filters = {}

	for dt in doctypes:
		filter_list = frappe.desk.reportview.build_match_conditions(dt, user, False)
		if filter_list:
			match_filters[dt] = filter_list

	return match_filters


def validate_filters_permissions(report_name, filters=None, user=None):
	if not filters:
		return

	if isinstance(filters, str):
		filters = json.loads(filters)

	report = frappe.get_doc("Report", report_name)
	for field in report.filters:
		if field.fieldname in filters and field.fieldtype == "Link":
			linked_doctype = field.options
			if not has_permission(
				doctype=linked_doctype, ptype="read", doc=filters[field.fieldname], user=user
			) and not has_permission(
				doctype=linked_doctype, ptype="select", doc=filters[field.fieldname], user=user
			):
				frappe.throw(
					_("You do not have permission to access {0}: {1}.").format(
						linked_doctype, filters[field.fieldname]
					)
				)


def translate_report_data(data, total_row):
	for d in data[:-1] if total_row else data:
		for field, value in d.items():
			if isinstance(value, str):
				d[field] = _(value)
	return data
