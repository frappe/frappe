# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""build query for doclistview and return results"""

import json
from io import StringIO

import frappe
import frappe.permissions
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.model import child_table_fields, default_fields, get_permitted_fields, optional_fields
from frappe.model.base_document import get_controller
from frappe.model.db_query import DatabaseQuery
from frappe.model.utils import is_virtual_doctype
from frappe.utils import add_user_info, cstr, format_duration


@frappe.whitelist()
@frappe.read_only()
def get():
	args = get_form_params()
	# If virtual doctype get data from controller het_list method
	if is_virtual_doctype(args.doctype):
		controller = get_controller(args.doctype)
		data = compress(controller.get_list(args))
	else:
		data = compress(execute(**args), args=args)
	return data


@frappe.whitelist()
@frappe.read_only()
def get_list():
	args = get_form_params()

	if is_virtual_doctype(args.doctype):
		controller = get_controller(args.doctype)
		data = controller.get_list(args)
	else:
		# uncompressed (refactored from frappe.model.db_query.get_list)
		data = execute(**args)

	return data


@frappe.whitelist()
@frappe.read_only()
def get_count():
	args = get_form_params()

	if is_virtual_doctype(args.doctype):
		controller = get_controller(args.doctype)
		data = controller.get_count(args)
	else:
		distinct = "distinct " if args.distinct == "true" else ""
		args.fields = [f"count({distinct}`tab{args.doctype}`.name) as total_count"]
		data = execute(**args)[0].get("total_count")

	return data


def execute(doctype, *args, **kwargs):
	return DatabaseQuery(doctype).execute(*args, **kwargs)


def get_form_params():
	"""Stringify GET request parameters."""
	data = frappe._dict(frappe.local.form_dict)
	clean_params(data)
	validate_args(data)
	return data


def validate_args(data):
	parse_json(data)
	setup_group_by(data)

	validate_fields(data)
	if data.filters:
		validate_filters(data, data.filters)
	if data.or_filters:
		validate_filters(data, data.or_filters)

	data.strict = None

	return data


def validate_fields(data):
	wildcard = update_wildcard_field_param(data)

	for field in list(data.fields or []):
		fieldname = extract_fieldname(field)
		if is_standard(fieldname):
			continue

		meta, df = get_meta_and_docfield(fieldname, data)

		if not df:
			if wildcard:
				continue
			else:
				raise_invalid_field(fieldname)

		# remove the field from the query if the report hide flag is set and current view is Report
		if df.report_hide and data.view == "Report":
			data.fields.remove(field)
			continue

		if df.fieldname in [_df.fieldname for _df in meta.get_high_permlevel_fields()]:
			if df.get("permlevel") not in meta.get_permlevel_access(parenttype=data.doctype):
				data.fields.remove(field)


def validate_filters(data, filters):
	if isinstance(filters, list):
		# filters as list
		for condition in filters:
			if len(condition) == 3:
				# [fieldname, condition, value]
				fieldname = condition[0]
				if is_standard(fieldname):
					continue
				meta, df = get_meta_and_docfield(fieldname, data)
				if not df:
					raise_invalid_field(condition[0])
			else:
				# [doctype, fieldname, condition, value]
				fieldname = condition[1]
				if is_standard(fieldname):
					continue
				meta = frappe.get_meta(condition[0])
				if not meta.get_field(fieldname):
					raise_invalid_field(fieldname)

	else:
		for fieldname in filters:
			if is_standard(fieldname):
				continue
			meta, df = get_meta_and_docfield(fieldname, data)
			if not df:
				raise_invalid_field(fieldname)


def setup_group_by(data):
	"""Add columns for aggregated values e.g. count(name)"""
	if data.group_by and data.aggregate_function:
		if data.aggregate_function.lower() not in ("count", "sum", "avg"):
			frappe.throw(_("Invalid aggregate function"))

		if frappe.db.has_column(data.aggregate_on_doctype, data.aggregate_on_field):
			data.fields.append(
				f"{data.aggregate_function}(`tab{data.aggregate_on_doctype}`.`{data.aggregate_on_field}`) AS _aggregate_column"
			)
		else:
			raise_invalid_field(data.aggregate_on_field)

		data.pop("aggregate_on_doctype")
		data.pop("aggregate_on_field")
		data.pop("aggregate_function")


def raise_invalid_field(fieldname):
	frappe.throw(_("Field not permitted in query") + f": {fieldname}", frappe.DataError)


def is_standard(fieldname):
	if "." in fieldname:
		fieldname = fieldname.split(".")[1].strip("`")
	return (
		fieldname in default_fields or fieldname in optional_fields or fieldname in child_table_fields
	)


def extract_fieldname(field):
	for text in (",", "/*", "#"):
		if text in field:
			raise_invalid_field(field)

	fieldname = field
	for sep in (" as ", " AS "):
		if sep in fieldname:
			fieldname = fieldname.split(sep, 1)[0]

	# certain functions allowed, extract the fieldname from the function
	if fieldname.startswith("count(") or fieldname.startswith("sum(") or fieldname.startswith("avg("):
		if not fieldname.strip().endswith(")"):
			raise_invalid_field(field)
		fieldname = fieldname.split("(", 1)[1][:-1]

	return fieldname


def get_meta_and_docfield(fieldname, data):
	parenttype, fieldname = get_parenttype_and_fieldname(fieldname, data)
	meta = frappe.get_meta(parenttype)
	df = meta.get_field(fieldname)
	return meta, df


def update_wildcard_field_param(data):
	if (isinstance(data.fields, str) and data.fields == "*") or (
		isinstance(data.fields, (list, tuple)) and len(data.fields) == 1 and data.fields[0] == "*"
	):
		if frappe.get_system_settings("apply_perm_level_on_api_calls"):
			data.fields = get_permitted_fields(data.doctype, parenttype=data.parenttype)
		else:
			data.fields = frappe.db.get_table_columns(data.doctype)
		return True

	return False


def clean_params(data):
	for param in ("cmd", "data", "ignore_permissions", "view", "user", "csrf_token", "join"):
		data.pop(param, None)


def parse_json(data):
	if (filters := data.get("filters")) and isinstance(filters, str):
		data["filters"] = json.loads(filters)
	if (or_filters := data.get("or_filters")) and isinstance(or_filters, str):
		data["or_filters"] = json.loads(or_filters)
	if (fields := data.get("fields")) and isinstance(fields, str):
		data["fields"] = ["*"] if fields == "*" else json.loads(fields)
	if isinstance(data.get("docstatus"), str):
		data["docstatus"] = json.loads(data["docstatus"])
	if isinstance(data.get("save_user_settings"), str):
		data["save_user_settings"] = json.loads(data["save_user_settings"])
	else:
		data["save_user_settings"] = True


def get_parenttype_and_fieldname(field, data):
	if "." in field:
		parts = field.split(".")
		parenttype = parts[0]
		fieldname = parts[1]
		if parenttype.startswith("`tab"):
			# `tabChild DocType`.`fieldname`
			parenttype = parenttype[4:-1]
			fieldname = fieldname.strip("`")
		else:
			# tablefield.fieldname
			parenttype = frappe.get_meta(data.doctype).get_field(parenttype).options
	else:
		parenttype = data.doctype
		fieldname = field.strip("`")

	return parenttype, fieldname


def compress(data, args=None):
	"""separate keys and values"""
	from frappe.desk.query_report import add_total_row

	user_info = {}

	if not data:
		return data
	if args is None:
		args = {}
	values = []
	keys = list(data[0])
	for row in data:
		new_row = []
		for key in keys:
			new_row.append(row.get(key))
		values.append(new_row)

		# add user info for assignments (avatar)
		if row.get("_assign", ""):
			for user in json.loads(row._assign):
				add_user_info(user, user_info)

	if args.get("add_total_row"):
		meta = frappe.get_meta(args.doctype)
		values = add_total_row(values, keys, meta)

	return {"keys": keys, "values": values, "user_info": user_info}


@frappe.whitelist()
def save_report(name, doctype, report_settings):
	"""Save reports of type Report Builder from Report View"""

	if frappe.db.exists("Report", name):
		report = frappe.get_doc("Report", name)
		if report.is_standard == "Yes":
			frappe.throw(_("Standard Reports cannot be edited"))

		if report.report_type != "Report Builder":
			frappe.throw(_("Only reports of type Report Builder can be edited"))

		if report.owner != frappe.session.user and not report.has_permission("write"):
			frappe.throw(_("Insufficient Permissions for editing Report"), frappe.PermissionError)
	else:
		report = frappe.new_doc("Report")
		report.report_name = name
		report.ref_doctype = doctype

	report.report_type = "Report Builder"
	report.json = report_settings
	report.save(ignore_permissions=True)
	frappe.msgprint(
		_("Report {0} saved").format(frappe.bold(report.name)),
		indicator="green",
		alert=True,
	)
	return report.name


@frappe.whitelist()
def delete_report(name):
	"""Delete reports of type Report Builder from Report View"""

	report = frappe.get_doc("Report", name)
	if report.is_standard == "Yes":
		frappe.throw(_("Standard Reports cannot be deleted"))

	if report.report_type != "Report Builder":
		frappe.throw(_("Only reports of type Report Builder can be deleted"))

	if report.owner != frappe.session.user and not report.has_permission("delete"):
		frappe.throw(_("Insufficient Permissions for deleting Report"), frappe.PermissionError)

	report.delete(ignore_permissions=True)
	frappe.msgprint(
		_("Report {0} deleted").format(frappe.bold(report.name)),
		indicator="green",
		alert=True,
	)


@frappe.whitelist()
@frappe.read_only()
def export_query():
	"""export from report builder"""
	title = frappe.form_dict.title
	frappe.form_dict.pop("title", None)

	form_params = get_form_params()
	form_params["limit_page_length"] = None
	form_params["as_list"] = True
	doctype = form_params.doctype
	add_totals_row = None
	file_format_type = form_params["file_format_type"]
	title = title or doctype

	del form_params["doctype"]
	del form_params["file_format_type"]

	if "add_totals_row" in form_params and form_params["add_totals_row"] == "1":
		add_totals_row = 1
		del form_params["add_totals_row"]

	frappe.permissions.can_export(doctype, raise_exception=True)

	if "selected_items" in form_params:
		si = json.loads(frappe.form_dict.get("selected_items"))
		form_params["filters"] = {"name": ("in", si)}
		del form_params["selected_items"]

	make_access_log(
		doctype=doctype,
		file_type=file_format_type,
		report_name=form_params.report_name,
		filters=form_params.filters,
	)

	db_query = DatabaseQuery(doctype)
	ret = db_query.execute(**form_params)

	if add_totals_row:
		ret = append_totals_row(ret)

	data = [[_("Sr")] + get_labels(db_query.fields, doctype)]
	for i, row in enumerate(ret):
		data.append([i + 1] + list(row))

	data = handle_duration_fieldtype_values(doctype, data, db_query.fields)

	if file_format_type == "CSV":

		# convert to csv
		import csv

		from frappe.utils.xlsxutils import handle_html

		f = StringIO()
		writer = csv.writer(f)
		for r in data:
			# encode only unicode type strings and not int, floats etc.
			writer.writerow([handle_html(frappe.as_unicode(v)) if isinstance(v, str) else v for v in r])

		f.seek(0)
		frappe.response["result"] = cstr(f.read())
		frappe.response["type"] = "csv"
		frappe.response["doctype"] = title

	elif file_format_type == "Excel":

		from frappe.utils.xlsxutils import make_xlsx

		xlsx_file = make_xlsx(data, doctype)

		frappe.response["filename"] = _(title) + ".xlsx"
		frappe.response["filecontent"] = xlsx_file.getvalue()
		frappe.response["type"] = "binary"


def append_totals_row(data):
	if not data:
		return data
	data = list(data)
	totals = []
	totals.extend([""] * len(data[0]))

	for row in data:
		for i in range(len(row)):
			if isinstance(row[i], (float, int)):
				totals[i] = (totals[i] or 0) + row[i]

	if not isinstance(totals[0], (int, float)):
		totals[0] = "Total"

	data.append(totals)

	return data


def get_labels(fields, doctype):
	"""get column labels based on column names"""
	labels = []
	for key in fields:
		key = key.split(" as ")[0]

		if key.startswith(("count(", "sum(", "avg(")):
			continue

		if "." in key:
			parenttype, fieldname = key.split(".")[0][4:-1], key.split(".")[1].strip("`")
		else:
			parenttype = doctype
			fieldname = fieldname.strip("`")

		if parenttype == doctype and fieldname == "name":
			label = _("ID", context="Label of name column in report")
		else:
			df = frappe.get_meta(parenttype).get_field(fieldname)
			label = _(df.label if df else fieldname.title())
			if parenttype != doctype:
				# If the column is from a child table, append the child doctype.
				# For example, "Item Code (Sales Invoice Item)".
				label += f" ({ _(parenttype) })"

		labels.append(label)

	return labels


def handle_duration_fieldtype_values(doctype, data, fields):
	for field in fields:
		key = field.split(" as ")[0]

		if key.startswith(("count(", "sum(", "avg(")):
			continue

		if "." in key:
			parenttype, fieldname = key.split(".")[0][4:-1], key.split(".")[1].strip("`")
		else:
			parenttype = doctype
			fieldname = field.strip("`")

		df = frappe.get_meta(parenttype).get_field(fieldname)

		if df and df.fieldtype == "Duration":
			index = fields.index(field) + 1
			for i in range(1, len(data)):
				val_in_seconds = data[i][index]
				if val_in_seconds:
					duration_val = format_duration(val_in_seconds, df.hide_days)
					data[i][index] = duration_val
	return data


@frappe.whitelist()
def delete_items():
	"""delete selected items"""
	import json

	items = sorted(json.loads(frappe.form_dict.get("items")), reverse=True)
	doctype = frappe.form_dict.get("doctype")

	if len(items) > 10:
		frappe.enqueue("frappe.desk.reportview.delete_bulk", doctype=doctype, items=items)
	else:
		delete_bulk(doctype, items)


def delete_bulk(doctype, items):
	for i, d in enumerate(items):
		try:
			frappe.delete_doc(doctype, d)
			if len(items) >= 5:
				frappe.publish_realtime(
					"progress",
					dict(progress=[i + 1, len(items)], title=_("Deleting {0}").format(doctype), description=d),
					user=frappe.session.user,
				)
			# Commit after successful deletion
			frappe.db.commit()
		except Exception:
			# rollback if any record failed to delete
			# if not rollbacked, queries get committed on after_request method in app.py
			frappe.db.rollback()


@frappe.whitelist()
@frappe.read_only()
def get_sidebar_stats(stats, doctype, filters=None):
	if filters is None:
		filters = []

	if is_virtual_doctype(doctype):
		controller = get_controller(doctype)
		args = {"stats": stats, "filters": filters}
		data = controller.get_stats(args)
	else:
		data = get_stats(stats, doctype, filters)

	return {"stats": data}


@frappe.whitelist()
@frappe.read_only()
def get_stats(stats, doctype, filters=None):
	"""get tag info"""
	import json

	if filters is None:
		filters = []
	columns = json.loads(stats)
	if filters:
		filters = json.loads(filters)
	results = {}

	try:
		db_columns = frappe.db.get_table_columns(doctype)
	except (frappe.db.InternalError, frappe.db.ProgrammingError):
		# raised when _user_tags column is added on the fly
		# raised if its a virtual doctype
		db_columns = []

	for column in columns:
		if column not in db_columns:
			continue
		try:
			tag_count = frappe.get_list(
				doctype,
				fields=[column, "count(*)"],
				filters=filters + [[column, "!=", ""]],
				group_by=column,
				as_list=True,
				distinct=1,
			)

			if column == "_user_tags":
				results[column] = scrub_user_tags(tag_count)
				no_tag_count = frappe.get_list(
					doctype,
					fields=[column, "count(*)"],
					filters=filters + [[column, "in", ("", ",")]],
					as_list=True,
					group_by=column,
					order_by=column,
				)

				no_tag_count = no_tag_count[0][1] if no_tag_count else 0

				results[column].append([_("No Tags"), no_tag_count])
			else:
				results[column] = tag_count

		except frappe.db.SQLError:
			pass
		except frappe.db.InternalError as e:
			# raised when _user_tags column is added on the fly
			pass

	return results


@frappe.whitelist()
def get_filter_dashboard_data(stats, doctype, filters=None):
	"""get tags info"""
	import json

	tags = json.loads(stats)
	filters = json.loads(filters or [])
	stats = {}

	columns = frappe.db.get_table_columns(doctype)
	for tag in tags:
		if not tag["name"] in columns:
			continue
		tagcount = []
		if tag["type"] not in ["Date", "Datetime"]:
			tagcount = frappe.get_list(
				doctype,
				fields=[tag["name"], "count(*)"],
				filters=filters + ["ifnull(`%s`,'')!=''" % tag["name"]],
				group_by=tag["name"],
				as_list=True,
			)

		if tag["type"] not in [
			"Check",
			"Select",
			"Date",
			"Datetime",
			"Int",
			"Float",
			"Currency",
			"Percent",
		] and tag["name"] not in ["docstatus"]:
			stats[tag["name"]] = list(tagcount)
			if stats[tag["name"]]:
				data = [
					"No Data",
					frappe.get_list(
						doctype,
						fields=[tag["name"], "count(*)"],
						filters=filters + ["({0} = '' or {0} is null)".format(tag["name"])],
						as_list=True,
					)[0][1],
				]
				if data and data[1] != 0:

					stats[tag["name"]].append(data)
		else:
			stats[tag["name"]] = tagcount

	return stats


def scrub_user_tags(tagcount):
	"""rebuild tag list for tags"""
	rdict = {}
	tagdict = dict(tagcount)
	for t in tagdict:
		if not t:
			continue
		alltags = t.split(",")
		for tag in alltags:
			if tag:
				if tag not in rdict:
					rdict[tag] = 0

				rdict[tag] += tagdict[t]

	rlist = []
	for tag in rdict:
		rlist.append([tag, rdict[tag]])

	return rlist


# used in building query in queries.py
def get_match_cond(doctype, as_condition=True):
	cond = DatabaseQuery(doctype).build_match_conditions(as_condition=as_condition)
	if not as_condition:
		return cond

	return ((" and " + cond) if cond else "").replace("%", "%%")


def build_match_conditions(doctype, user=None, as_condition=True):
	match_conditions = DatabaseQuery(doctype, user=user).build_match_conditions(
		as_condition=as_condition
	)
	if as_condition:
		return match_conditions.replace("%", "%%")
	return match_conditions


def get_filters_cond(
	doctype, filters, conditions, ignore_permissions=None, with_match_conditions=False
):
	if isinstance(filters, str):
		filters = json.loads(filters)

	if filters:
		flt = filters
		if isinstance(filters, dict):
			filters = filters.items()
			flt = []
			for f in filters:
				if isinstance(f[1], str) and f[1][0] == "!":
					flt.append([doctype, f[0], "!=", f[1][1:]])
				elif isinstance(f[1], (list, tuple)) and f[1][0].lower() in (
					"=",
					">",
					"<",
					">=",
					"<=",
					"!=",
					"like",
					"not like",
					"in",
					"not in",
					"between",
					"is",
				):

					flt.append([doctype, f[0], f[1][0], f[1][1]])
				else:
					flt.append([doctype, f[0], "=", f[1]])

		query = DatabaseQuery(doctype)
		query.filters = flt
		query.conditions = conditions

		if with_match_conditions:
			query.build_match_conditions()

		query.build_filter_conditions(flt, conditions, ignore_permissions)

		cond = " and " + " and ".join(query.conditions)
	else:
		cond = ""
	return cond
