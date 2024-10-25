# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# model __init__.py
import frappe
from frappe import _, _lt

data_fieldtypes = (
	"Currency",
	"Int",
	"Long Int",
	"Float",
	"Percent",
	"Check",
	"Small Text",
	"Long Text",
	"Code",
	"Text Editor",
	"Markdown Editor",
	"HTML Editor",
	"Date",
	"Datetime",
	"Time",
	"Text",
	"Data",
	"Link",
	"Dynamic Link",
	"Password",
	"Select",
	"Rating",
	"Read Only",
	"Attach",
	"Attach Image",
	"Signature",
	"Color",
	"Barcode",
	"Geolocation",
	"Duration",
	"Icon",
	"Phone",
	"Autocomplete",
	"JSON",
)

float_like_fields = {"Float", "Currency", "Percent"}
datetime_fields = {"Datetime", "Date", "Time"}

attachment_fieldtypes = (
	"Attach",
	"Attach Image",
)

no_value_fields = (
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Table",
	"Table MultiSelect",
	"Button",
	"Image",
	"Fold",
	"Heading",
)

display_fieldtypes = (
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Image",
	"Fold",
	"Heading",
)

numeric_fieldtypes = ("Currency", "Int", "Long Int", "Float", "Percent", "Check")

data_field_options = ("Email", "Name", "Phone", "URL", "Barcode")

default_fields = (
	"doctype",
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
)

child_table_fields = ("parent", "parentfield", "parenttype")

optional_fields = ("_user_tags", "_comments", "_assign", "_liked_by", "_seen")

table_fields = ("Table", "Table MultiSelect")

core_doctypes_list = (
	"DefaultValue",
	"DocType",
	"DocField",
	"DocPerm",
	"DocType Action",
	"DocType Link",
	"User",
	"Role",
	"Has Role",
	"Page",
	"Module Def",
	"Print Format",
	"Report",
	"Customize Form",
	"Customize Form Field",
	"Property Setter",
	"Custom Field",
	"Client Script",
)

log_types = (
	"Version",
	"Error Log",
	"Scheduled Job Log",
	"Event Sync Log",
	"Event Update Log",
	"Access Log",
	"View Log",
	"Activity Log",
	"Energy Point Log",
	"Notification Log",
	"Email Queue",
	"DocShare",
	"Document Follow",
	"Console Log",
)

std_fields = [
	{"fieldname": "name", "fieldtype": "Link", "label": "ID"},
	{"fieldname": "owner", "fieldtype": "Link", "label": "Created By", "options": "User"},
	{"fieldname": "idx", "fieldtype": "Int", "label": "Index"},
	{"fieldname": "creation", "fieldtype": "Datetime", "label": "Created On"},
	{"fieldname": "modified", "fieldtype": "Datetime", "label": "Last Updated On"},
	{
		"fieldname": "modified_by",
		"fieldtype": "Link",
		"label": "Last Updated By",
		"options": "User",
	},
	{"fieldname": "_user_tags", "fieldtype": "Data", "label": "Tags"},
	{"fieldname": "_liked_by", "fieldtype": "Data", "label": "Liked By"},
	{"fieldname": "_comments", "fieldtype": "Text", "label": "Comments"},
	{"fieldname": "_assign", "fieldtype": "Text", "label": "Assigned To"},
	{"fieldname": "docstatus", "fieldtype": "Int", "label": "Document Status"},
]


def delete_fields(args_dict, delete: int = 0) -> None:
	"""
	Delete a field.
	* Deletes record from `tabDocField`
	* If not single doctype: Drops column from table
	* If single, deletes record from `tabSingles`
	args_dict = { dt: [field names] }
	"""
	import frappe.utils

	for dt in args_dict:
		fields = args_dict[dt]
		if not fields:
			continue

		frappe.db.delete(
			"DocField",
			{
				"parent": dt,
				"fieldname": ("in", fields),
			},
		)

		# Delete the data/column only if delete is specified
		if not delete:
			continue

		if frappe.db.get_value("DocType", dt, "issingle"):
			frappe.db.delete(
				"Singles",
				{
					"doctype": dt,
					"field": ("in", fields),
				},
			)
		else:
			existing_fields = frappe.db.describe(dt)
			existing_fields = existing_fields and [e[0] for e in existing_fields] or []
			fields_need_to_delete = set(fields) & set(existing_fields)
			if not fields_need_to_delete:
				continue

			if frappe.db.db_type == "mariadb":
				# mariadb implicitly commits before DDL, make it explicit
				frappe.db.commit()

			query = "ALTER TABLE `tab%s` " % dt + ", ".join(
				"DROP COLUMN `%s`" % f for f in fields_need_to_delete
			)
			frappe.db.sql(query)

		if frappe.db.db_type == "postgres":
			# commit the results to db
			frappe.db.commit()


def get_permitted_fields(
	doctype: str,
	parenttype: str | None = None,
	user: str | None = None,
	permission_type: str | None = None,
	*,
	ignore_virtual: bool = False,
) -> list[str]:
	meta = frappe.get_meta(doctype)
	valid_columns = meta.get_valid_columns()

	if doctype in core_doctypes_list:
		return valid_columns

	# DocType has only fields of type Table (Table, Table MultiSelect)
	if set(valid_columns).issubset(default_fields):
		return valid_columns

	if permission_type is None:
		permission_type = "select" if frappe.only_has_select_perm(doctype, user=user) else "read"

	meta_fields = meta.default_fields.copy()
	optional_meta_fields = [x for x in optional_fields if x in valid_columns]

	if permitted_fields := meta.get_permitted_fieldnames(
		parenttype=parenttype,
		user=user,
		permission_type=permission_type,
		with_virtual_fields=not ignore_virtual,
	):
		if permission_type == "select":
			return permitted_fields

		if meta.istable:
			meta_fields.extend(child_table_fields)

		return meta_fields + permitted_fields + optional_meta_fields

	return meta_fields + optional_meta_fields


def is_default_field(fieldname: str) -> bool:
	return fieldname in default_fields
