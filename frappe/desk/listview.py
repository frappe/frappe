# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model import is_default_field
from frappe.query_builder import Order
from frappe.query_builder.functions import Count
from frappe.query_builder.terms import SubQuery
from frappe.query_builder.utils import DocType


@frappe.whitelist()
def get_list_settings(doctype):
	try:
		return frappe.get_cached_doc("List View Settings", doctype)
	except frappe.DoesNotExistError:
		frappe.clear_messages()


@frappe.whitelist()
def set_list_settings(doctype, values):
	try:
		doc = frappe.get_doc("List View Settings", doctype)
	except frappe.DoesNotExistError:
		doc = frappe.new_doc("List View Settings")
		doc.name = doctype
		frappe.clear_messages()
	doc.update(frappe.parse_json(values))
	doc.save()


@frappe.whitelist()
def get_group_by_count(doctype: str, current_filters: str, field: str) -> list[dict]:
	current_filters = frappe.parse_json(current_filters)

	if field == "_assign":
		return get_assign_count(doctype, current_filters)

	if (
		not frappe.get_meta(doctype).has_field(field)
		and not is_default_field(field)
		and not field == "_user_tags"
	):
		raise ValueError("Field does not belong to doctype")

	result = frappe.get_list(
		doctype,
		filters=current_filters,
		group_by=f"`tab{doctype}`.{field}",
		fields=["count(*) as count", f"`{field}` as name"],
		order_by="count desc",
		limit=50,
	)

	if field == "_user_tags":
		result = compile_tags(result)

	return result


def get_assign_count(doctype, current_filters):
	ToDo = DocType("ToDo")
	User = DocType("User")
	count = Count("*").as_("count")
	filtered_records = frappe.qb.get_query(
		doctype,
		filters=current_filters,
		fields=["name"],
		validate_filters=True,
	)

	return (
		frappe.qb.from_(ToDo)
		.from_(User)
		.select(ToDo.allocated_to.as_("name"), count)
		.where(
			(ToDo.status != "Cancelled")
			& (ToDo.allocated_to == User.name)
			& (User.user_type == "System User")
			& (ToDo.reference_name.isin(SubQuery(filtered_records)))
		)
		.groupby(ToDo.allocated_to)
		.orderby(count, order=Order.desc)
		.limit(50)
		.run(as_dict=True)
	)


def compile_tags(result):
	"""rebuild tags result with individual tags

	tags can be like `test1,test2` or just `,test1`.
	This method will split tags and tally count for each tag
	"""
	compiled = []
	for tag in result:
		if not tag["name"]:
			# no tags
			compiled.append(tag)
		else:
			tags = tag["name"].split(",")
			for _tag in tags:
				if _tag:
					found = False
					for c in compiled:
						# already added by some different combo
						if c["name"] == _tag:
							c["count"] += tag["count"]
							found = True

					if not found:
						compiled.append({"name": _tag, "count": tag["count"]})

	return compiled
