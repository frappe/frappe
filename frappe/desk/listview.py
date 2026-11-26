# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
from typing import Any

import frappe
from frappe import _
from frappe.database.query import _cast_autoincrement_name
from frappe.model import is_default_field
from frappe.model.utils.mask import as_aliased_field, mask_dict_results
from frappe.query_builder import Field, Order
from frappe.query_builder.functions import Avg, Count, Max, Min, Sum
from frappe.query_builder.terms import SubQuery
from frappe.query_builder.utils import DocType
from frappe.utils import cint


@frappe.whitelist()
def get_list_settings(doctype: str):
	try:
		return frappe.get_cached_doc("List View Settings", doctype)
	except frappe.DoesNotExistError:
		frappe.clear_messages()


@frappe.whitelist()
def set_list_settings(doctype: str, values: str | dict[str, Any]):
	try:
		doc = frappe.get_doc("List View Settings", doctype)
	except frappe.DoesNotExistError:
		doc = frappe.new_doc("List View Settings")
		doc.name = doctype
		frappe.clear_messages()
	doc.update(frappe.parse_json(values))
	doc.save()


ASSIGNED_TO = "_assign"
AGGREGATES = {"COUNT": Count, "SUM": Sum, "AVG": Avg, "MIN": Min, "MAX": Max}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@frappe.whitelist()
def get_assignee_groups(
	doctype: str,
	fields: str | list,
	group_by: str,
	filters: str | list | dict | None = None,
	order_by: str | None = None,
	limit_start: int | str = 0,
	limit_page_length: int | str = 20,
) -> list[dict]:
	"""Grouped rows like `frappe.client.get_list`, a record counting under each of its assignees."""
	group_fields = [f.strip() for f in group_by.split(",")]
	if ASSIGNED_TO not in group_fields or not all(IDENTIFIER.match(f) for f in group_fields):
		frappe.throw(_("Group by must be fieldnames including {0}").format(ASSIGNED_TO))
	aggregates = [_parse_aggregate(f) for f in frappe.parse_json(fields) if isinstance(f, dict)]

	# The matching records the user can read, with the columns the groups need.
	columns = {f for f in group_fields if f != ASSIGNED_TO} | {
		fieldname for _fn, fieldname, _as in aggregates
	}
	columns.discard("name")
	name = _cast_autoincrement_name(DocType(doctype).name, doctype).as_("name")
	records = frappe.qb.get_query(
		doctype,
		filters=frappe.parse_json(filters),
		fields=[name, *sorted(columns)],
		ignore_permissions=False,
	).as_("records")

	# Each record's users, from its open assignments as `_assign` is kept.
	ToDo = DocType("ToDo")
	assignments = (
		frappe.qb.from_(ToDo)
		.select(ToDo.reference_name, ToDo.allocated_to)
		.distinct()
		.where(
			(ToDo.reference_type == doctype)
			& ToDo.status.notin(("Cancelled", "Closed"))
			& ToDo.allocated_to.isnotnull()
			& (ToDo.allocated_to != "")
		)
	).as_("assignments")

	terms = {
		f: Field("allocated_to", table=assignments) if f == ASSIGNED_TO else Field(f, table=records)
		for f in group_fields
	}
	for fn, fieldname, alias in aggregates:
		terms[alias] = AGGREGATES[fn](Field(fieldname, table=records))

	query = (
		frappe.qb.from_(records)
		.left_join(assignments)
		.on(Field("reference_name", table=assignments) == Field("name", table=records))
		.select(*(term.as_(key) for key, term in terms.items()))
		.groupby(*(terms[f] for f in group_fields))
	)
	for part in (order_by or "").split(","):
		if not part.strip():
			continue
		key, _sep, direction = part.strip().partition(" ")
		direction = direction.strip().lower() or "asc"
		if key not in terms or direction not in ("asc", "desc"):
			frappe.throw(_("Cannot sort groups by {0}").format(part.strip()))
		query = query.orderby(terms[key], order=Order[direction])
	if limit := cint(limit_page_length):
		query = query.limit(limit).offset(cint(limit_start))

	rows = query.run(as_dict=True)
	masked = {df.fieldname: df for df in frappe.get_meta(doctype).get_masked_fields()}
	to_mask = [masked[f] for f in group_fields if f in masked] + [
		as_aliased_field(masked[fieldname], alias)
		for fn, fieldname, alias in aggregates
		if fieldname in masked and fn != "COUNT"
	]
	return mask_dict_results(rows, to_mask) if to_mask else rows


# `{"SUM": "amount", "as": "total"}`, as `frappe.client.get_list` takes it, as (function, fieldname, alias).
def _parse_aggregate(field: dict) -> tuple[str, str, str]:
	alias = field.get("as")
	functions = [(fn, fieldname) for fn, fieldname in field.items() if fn != "as"]
	if (
		len(functions) != 1
		or functions[0][0].upper() not in AGGREGATES
		or not isinstance(functions[0][1], str)
		or not IDENTIFIER.match(functions[0][1])
		or not isinstance(alias, str)
		or not IDENTIFIER.match(alias)
	):
		frappe.throw(_("Invalid aggregate {0}").format(frappe.as_json(field)))
	fn, fieldname = functions[0]
	return fn.upper(), fieldname, alias


@frappe.whitelist()
def get_group_by_count(doctype: str, current_filters: str | list, field: str) -> list[dict]:
	current_filters = frappe.parse_json(current_filters)

	if field == "assigned_to":
		ToDo = DocType("ToDo")
		User = DocType("User")
		count = Count("*").as_("count")
		filtered_records = frappe.qb.get_query(
			doctype,
			filters=current_filters,
			fields=[_cast_autoincrement_name(DocType(doctype).name, doctype)],
			ignore_permissions=False,
		)

		query = (
			frappe.qb.from_(ToDo)
			.from_(User)
			.select(ToDo.allocated_to.as_("name"), count)
			.where(
				ToDo.status.notin(("Cancelled", "Closed"))
				& (ToDo.allocated_to == User.name)
				& (User.user_type == "System User")
				& (ToDo.reference_type == doctype)
				& (ToDo.reference_name.isin(SubQuery(filtered_records)))
			)
			.groupby(ToDo.allocated_to)
			.orderby(count, order=Order.desc)
			.limit(50)
		)
		user_meta = frappe.get_meta("User")
		if user_meta.show_title_field_in_link:
			title = User[user_meta.get_title_field()]
			query = query.select(title.as_("title")).groupby(title)

		return query.run(as_dict=True)

	meta = frappe.get_meta(doctype)

	if not meta.has_field(field) and not is_default_field(field):
		raise ValueError("Field does not belong to doctype")

	data = frappe.get_list(
		doctype,
		filters=current_filters,
		group_by=field,
		fields=[{"COUNT": "*", "as": "count"}, f"{field} as name"],
		order_by="count desc",
		limit=1000,
	)

	if field == "owner":
		owner_idx = None

		for idx, item in enumerate(data):
			if item.name == frappe.session.user:
				owner_idx = idx
				break

		if owner_idx:
			data = [data.pop(owner_idx), *data[0:49]]
		else:
			data = data[0:50]
	else:
		data = data[0:50]

	# Add in title if it's a link field and `show_title_field_in_link` is set
	if field in ("owner", "modified_by"):
		link_doctype = "User"
	elif (field_meta := meta.get_field(field)) and field_meta.fieldtype == "Link":
		link_doctype = field_meta.options
	else:
		link_doctype = None

	if link_doctype and (link_meta := frappe.get_meta(link_doctype)).show_title_field_in_link:
		title_field = link_meta.get_title_field()
		titles = dict(
			frappe.get_all(
				link_doctype,
				filters={"name": ("in", [item.name for item in data])},
				fields=["name", title_field],
				as_list=True,
			)
		)
		for item in data:
			item.title = titles.get(item.name)

	return data
