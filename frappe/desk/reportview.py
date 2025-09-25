# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""build query for doclistview and return results"""

import json
from functools import lru_cache

from sql_metadata import Parser

import frappe
import frappe.permissions
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.model import child_table_fields, default_fields, get_permitted_fields, optional_fields
from frappe.model.base_document import get_controller
from frappe.model.db_query import DatabaseQuery
from frappe.model.utils import is_virtual_doctype
from frappe.utils import add_user_info, cint, format_duration
from frappe.utils.data import sbool

DISALLOWED_PARAMS = ("cmd", "data", "ignore_permissions", "view", "user", "csrf_token", "join")


@frappe.whitelist()
@frappe.read_only()
def get():
	args = get_form_params()
	# If virtual doctype, get data from controller get_list method
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
def get_count() -> int:
	args = get_form_params()

	if is_virtual_doctype(args.doctype):
		controller = get_controller(args.doctype)
		count = controller.get_count(args)
	else:
		args.distinct = sbool(args.distinct)
		distinct = "distinct " if args.distinct else ""
		args.limit = cint(args.limit)
		fieldname = f"{distinct}`tab{args.doctype}`.name"
		args.order_by = None

		args.fields = [fieldname]
		partial_query = execute(**args, run=0)
		count = frappe.db.sql(f"""select count(*) from ( {partial_query} ) p""")[0][0]

	return count


def execute(doctype, *args, **kwargs):
	return DatabaseQuery(doctype).execute(*args, **kwargs)


def get_form_params():
	"""parse GET request parameters."""
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
		fieldname = extract_fieldnames(field)[0]
		if not fieldname:
			raise_invalid_field(fieldname)

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
	return fieldname in default_fields or fieldname in optional_fields or fieldname in child_table_fields


@lru_cache
def extract_fieldnames(field):
	from frappe.database.schema import SPECIAL_CHAR_PATTERN

	if not SPECIAL_CHAR_PATTERN.findall(field):
		return [field]

	columns = Parser(f"select {field} from _dummy").columns

	if not columns:
		f = field.lower()
		if ("count(" in f or "sum(" in f or "avg(" in f) and "*" in f:
			return ["*"]

	return columns


def get_meta_and_docfield(fieldname, data):
	parenttype, fieldname = get_parenttype_and_fieldname(fieldname, data)
	meta = frappe.get_meta(parenttype)
	df = meta.get_field(fieldname)
	return meta, df


def update_wildcard_field_param(data):
	if (isinstance(data.fields, str) and data.fields == "*") or (
		isinstance(data.fields, list | tuple) and len(data.fields) == 1 and data.fields[0] == "*"
	):
		parent_type = data.parenttype or data.parent_doctype
		data.fields = get_permitted_fields(data.doctype, parenttype=parent_type, ignore_virtual=True)
		return True

	return False


def clean_params(data):
	for param in DISALLOWED_PARAMS:
		if param in data:
			del data[param]


def parse_json(data):
	if (filters := data.get("filters")) and isinstance(filters, str):
		data["filters"] = json.loads(filters)
	if (applied_filters := data.get("applied_filters")) and isinstance(applied_filters, str):
		data["applied_filters"] = json.loads(applied_filters)
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
		df = frappe.get_meta(data.doctype).get_field(parenttype)
		if not df and parenttype.startswith("tab"):
			# tabChild DocType.fieldname
			parenttype = parenttype[3:]
		else:
			# tablefield.fieldname
			parenttype = df.options
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
		values.append([row.get(key) for key in keys])

		# add user info for assignments (avatar)
		if row.get("_assign", ""):
			for user in json.loads(row._assign):
				add_user_info(user, user_info)

	if args.get("add_total_row"):
		meta = frappe.get_meta(args.doctype)
		values = add_total_row(values, keys, meta)

	return {"keys": keys, "values": values, "user_info": user_info}


@frappe.whitelist(methods=["POST", "PUT"])
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


@frappe.whitelist(methods=["POST", "DELETE"])
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
	from frappe.desk.utils import pop_csv_params

	form_params = get_form_params()
	form_params["limit_page_length"] = None
	form_params["as_list"] = True
	csv_params = pop_csv_params(form_params)
	export_in_background = int(form_params.pop("export_in_background", 0))

	if export_in_background:
		user = frappe.session.user
		user_email = frappe.get_cached_value("User", user, "email")
		frappe.enqueue(
			"frappe.desk.reportview.run_report_view_export_job",
			user_email=user_email,
			form_params=form_params,
			csv_params=csv_params,
			queue="long",
			now=frappe.flags.in_test,
		)

		frappe.msgprint(
			_(
				"Your report is being generated in the background. You will receive an email on {0} with a download link once it is ready."
			).format(user_email)
		)
		return

	return _export_query(form_params, csv_params)


def run_report_view_export_job(user_email, form_params, csv_params):
	from frappe.desk.utils import send_report_email

	report_name, file_extension, content = _export_query(form_params, csv_params, populate_response=False)
	send_report_email(user_email, report_name, file_extension, content, attached_to_name=report_name)


def _export_query(form_params, csv_params, populate_response=True):
	from frappe.desk.utils import get_csv_bytes, provide_binary_file
	from frappe.utils.xlsxutils import handle_html, make_xlsx

	doctype = form_params.pop("doctype")
	if isinstance(form_params["fields"], list):
		form_params["fields"].append("owner")
	elif isinstance(form_params["fields"], tuple):
		form_params["fields"] = form_params["fields"] + ("owner",)
	file_format_type = form_params.pop("file_format_type")
	title = form_params.pop("title", doctype)
	add_totals_row = 1 if form_params.pop("add_totals_row", None) == "1" else None
	translate_values = 1 if form_params.pop("translate_values", None) == "1" else None

	if selection := form_params.pop("selected_items", None):
		form_params["filters"] = {"name": ("in", json.loads(selection))}

	make_access_log(
		doctype=doctype,
		file_type=file_format_type,
		report_name=form_params.report_name,
		filters=form_params.filters,
	)

	db_query = DatabaseQuery(doctype)
	ret = db_query.execute(**form_params)

	if not frappe.permissions.can_export(doctype):
		if frappe.permissions.can_export(doctype, is_owner=True):
			for row in ret:
				if row[-1] != frappe.session.user:
					raise frappe.PermissionError(
						_("You are not allowed to export {} doctype").format(doctype)
					)
		else:
			raise frappe.PermissionError(_("You are not allowed to export {} doctype").format(doctype))

	if add_totals_row:
		ret = append_totals_row(ret)

	fields_info = get_field_info(db_query.fields, doctype)

	labels = [info["label"] for info in fields_info]
	data = [[_("Sr"), *labels]]
	processed_data = []

	if frappe.local.lang == "en" or not translate_values:
		data.extend([i + 1, *list(row)] for i, row in enumerate(ret))
	elif translate_values:
		translatable_fields = [field["translatable"] for field in fields_info]
		processed_data = []
		for i, row in enumerate(ret):
			processed_row = [i + 1] + [
				_(value) if translatable_fields[idx] else value for idx, value in enumerate(row)
			]
			processed_data.append(processed_row)
		data.extend(processed_data)

	data = handle_duration_fieldtype_values(doctype, data, db_query.fields)

	if file_format_type == "CSV":
		file_extension = "csv"
		content = get_csv_bytes(
			[[handle_html(frappe.as_unicode(v)) if isinstance(v, str) else v for v in r] for r in data],
			csv_params,
		)
	elif file_format_type == "Excel":
		file_extension = "xlsx"
		content = make_xlsx(data, doctype).getvalue()

	if not populate_response:
		return title, file_extension, content

	provide_binary_file(_(title), file_extension, content)


def append_totals_row(data):
	if not data:
		return data
	data = list(data)
	totals = []
	totals.extend([""] * len(data[0]))

	for row in data:
		for i in range(len(row)):
			if isinstance(row[i], float | int):
				totals[i] = (totals[i] or 0) + row[i]

	if not isinstance(totals[0], int | float):
		totals[0] = "Total"

	data.append(totals)

	return data


def get_field_info(fields, doctype):
	"""Get column names, labels, field types, and translatable properties based on column names."""

	field_info = []
	for key in fields:
		df = None
		try:
			parenttype, fieldname = parse_field(key)
		except ValueError:
			# handles aggregate functions
			parenttype = doctype
			fieldname = key.split("(", 1)[0]
			fieldname = fieldname[0].upper() + fieldname[1:]

		parenttype = parenttype or doctype

		if parenttype == doctype and fieldname == "name":
			name = fieldname
			label = _("ID", context="Label of name column in report")
			fieldtype = "Data"
			translatable = True
		else:
			df = frappe.get_meta(parenttype).get_field(fieldname)
			if df and df.fieldtype in ("Data", "Select", "Small Text", "Text"):
				name = df.name
				label = _(df.label)
				fieldtype = df.fieldtype
				translatable = getattr(df, "translatable", False)
			elif df and df.fieldtype == "Link" and frappe.get_meta(df.options).translated_doctype:
				name = df.name
				label = _(df.label)
				fieldtype = df.fieldtype
				translatable = True
			else:
				name = fieldname
				label = _(df.label) if df else _(fieldname)
				fieldtype = "Data"
				translatable = False

			if parenttype != doctype:
				# If the column is from a child table, append the child doctype.
				# For example, "Item Code (Sales Invoice Item)".
				label += f" ({_(parenttype)})"

		field_info.append(
			{"name": name, "label": label, "fieldtype": fieldtype, "translatable": translatable}
		)

	return field_info


def handle_duration_fieldtype_values(doctype, data, fields):
	for field in fields:
		try:
			parenttype, fieldname = parse_field(field)
		except ValueError:
			continue

		parenttype = parenttype or doctype
		df = frappe.get_meta(parenttype).get_field(fieldname)

		if df and df.fieldtype == "Duration":
			index = fields.index(field) + 1
			for i in range(1, len(data)):
				val_in_seconds = data[i][index]
				if val_in_seconds:
					duration_val = format_duration(val_in_seconds, df.hide_days)
					data[i][index] = duration_val
	return data


def parse_field(field: str) -> tuple[str | None, str]:
	"""Parse a field into parenttype and fieldname."""
	key = field.split(" as ", 1)[0]

	if key.startswith(("count(", "sum(", "avg(")):
		raise ValueError

	if "." in key:
		table, column = key.split(".", 2)[:2]
		return table[4:-1], column.strip("`")

	return None, key.strip("`")


@frappe.whitelist(methods=["POST", "DELETE"])
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
	undeleted_items = []
	for i, d in enumerate(items):
		try:
			frappe.delete_doc(doctype, d)
			if len(items) >= 5:
				frappe.publish_realtime(
					"progress",
					dict(
						progress=[i + 1, len(items)], title=_("Deleting {0}").format(doctype), description=d
					),
					user=frappe.session.user,
				)
			# Commit after successful deletion
			frappe.db.commit()
		except Exception:
			# rollback if any record failed to delete
			# if not rollbacked, queries get committed on after_request method in app.py
			undeleted_items.append(d)
			frappe.db.rollback()
	if undeleted_items and len(items) != len(undeleted_items):
		frappe.clear_messages()
		delete_bulk(doctype, undeleted_items)
	elif undeleted_items:
		frappe.msgprint(
			_("Failed to delete {0} documents: {1}").format(len(undeleted_items), ", ".join(undeleted_items)),
			realtime=True,
			title=_("Bulk Operation Failed"),
		)
	else:
		frappe.msgprint(
			_("Deleted all documents successfully"), realtime=True, title=_("Bulk Operation Successful")
		)


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
				filters=[*filters, [column, "!=", ""]],
				group_by=column,
				as_list=True,
				distinct=1,
			)

			if column == "_user_tags":
				results[column] = scrub_user_tags(tag_count)
				no_tag_count = frappe.get_list(
					doctype,
					fields=[column, "count(*)"],
					filters=[*filters, [column, "in", ("", ",")]],
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
		except frappe.db.InternalError:
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
		if tag["name"] not in columns:
			continue
		tagcount = []
		if tag["type"] not in ["Date", "Datetime"]:
			tagcount = frappe.get_list(
				doctype,
				fields=[tag["name"], "count(*)"],
				filters=[*filters, "ifnull(`{}`,'')!=''".format(tag["name"])],
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
						filters=[*filters, "({0} = '' or {0} is null)".format(tag["name"])],
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

	return [[tag, rdict[tag]] for tag in rdict]


# used in building query in queries.py
def get_match_cond(doctype, as_condition=True):
	cond = DatabaseQuery(doctype).build_match_conditions(as_condition=as_condition)
	if not as_condition:
		return cond

	return ((" and " + cond) if cond else "").replace("%", "%%")


def build_match_conditions(doctype, user=None, as_condition=True):
	match_conditions = DatabaseQuery(doctype, user=user).build_match_conditions(as_condition=as_condition)
	if as_condition:
		return match_conditions.replace("%", "%%")
	return match_conditions


def get_filters_cond(doctype, filters, conditions, ignore_permissions=None, with_match_conditions=False):
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
				elif isinstance(f[1], list | tuple) and f[1][0].lower() in (
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
