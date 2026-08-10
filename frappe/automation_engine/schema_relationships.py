# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Relationships derived from the schema, so no app has to restate its own link graph.

Link, child-table Link and Dynamic Link edges — in both directions — become relationships
automatically. Apps only register a provider for the edges the schema does not know about: a
name matched against a Data field, a union of two lookups, a dynamic reference narrowed to a
domain. An app definition of the same name wins over a derived one, so an app can also just
relabel what it inherits.

Incoming edges come from `frappe.desk.form.linked_with`, which is Redis-cached and already
checks that a Dynamic Link pair really does point at this DocType — deriving those from the
schema alone offers every dynamic reference in every installed app on every DocType.

Derived names embed the fieldname that backs them (`crm_deal_via_lead`) because the name is
persisted in saved flows: it has to stay stable as long as the field does.
"""

import frappe
from frappe import _
from frappe.automation_engine.relationships import AutomationRelationshipProvider
from frappe.utils.caching import request_cache

IGNORED_DOCTYPES = {
	"Access Log",
	"Activity Log",
	"Background Task",
	"Comment",
	"Communication Link",
	"Custom Field",
	"DocField",
	"DocPerm",
	"DocShare",
	"DocType",
	"Document Follow",
	"Document Share Key",
	"Email Queue",
	"Email Unsubscribe",
	"Energy Point Log",
	"Error Log",
	"File",
	"Integration Request",
	"Module Def",
	"Notification Log",
	"Notification Settings",
	"Permission Log",
	"Property Setter",
	"Role",
	"Route History",
	"Scheduled Job Log",
	"Submission Queue",
	"Tag Link",
	"Version",
	"View Log",
	"Webhook Request Log",
	"Workflow Action",
}


class SchemaRelationshipProvider(AutomationRelationshipProvider):
	"""Always registered, always consulted last."""

	def get_definitions(self, source_doctype: str) -> list[dict]:
		return list(derived_definitions(source_doctype))

	def resolve(self, source_doc, relationship: str, params: dict) -> list[dict]:
		definition = _derived(source_doc.doctype, relationship)
		resolver = FORWARD_RESOLVERS.get(definition["kind"])
		if not resolver:
			return self.query(source_doc, relationship, [], None)
		return resolver(source_doc, definition)

	def query(self, source_doc, relationship: str, filters: list, limit: int) -> list[dict]:
		definition = _derived(source_doc.doctype, relationship)
		if definition["kind"] not in REVERSE_KINDS:
			return super().query(source_doc, relationship, filters, limit)
		target = definition["target_doctype"]
		own = _reverse_filters(definition, source_doc)
		if own is None:
			return []
		names = frappe.get_list(target, filters=[*own, *(filters or [])], pluck="name", limit=limit)
		return [{"doctype": target, "name": name} for name in names]


# ---------------------------------------------------------------------------
# Outgoing edges — read straight off the loaded document.
# ---------------------------------------------------------------------------
def _resolve_link(doc, definition) -> list[dict]:
	return _references(definition["target_doctype"], [doc.get(definition["fieldname"])])


def _resolve_child_link(doc, definition) -> list[dict]:
	rows = doc.get(definition["table_fieldname"]) or []
	return _references(definition["target_doctype"], [row.get(definition["fieldname"]) for row in rows])


def _resolve_dynamic_link(doc, definition) -> list[dict]:
	"""The DocType is a field on the record, so it is only known now."""
	target = doc.get(definition["doctype_fieldname"])
	if target in _ignored():
		return []
	return _references(target, [doc.get(definition["fieldname"])])


FORWARD_RESOLVERS = {
	"link": _resolve_link,
	"child_link": _resolve_child_link,
	"dynamic_link": _resolve_dynamic_link,
}
REVERSE_KINDS = ("reverse_link", "reverse_child_link")


def _reverse_filters(definition, source_doc) -> list | None:
	"""Filters selecting the records pointing back at `source_doc`. None means "cannot match"."""
	if definition["kind"] != "reverse_child_link":
		return [[definition["fieldname"], "=", source_doc.name]]
	parents = _child_parents(definition, source_doc)
	return [["name", "in", parents]] if parents else None


def _child_parents(definition, source_doc) -> list[str]:
	"""The link sits on a child row, so find the owning parents first."""
	return frappe.get_all(
		definition["child_doctype"],
		filters={definition["fieldname"]: source_doc.name, "parenttype": definition["target_doctype"]},
		pluck="parent",
		distinct=True,
	)


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------
@request_cache
def derived_definitions(source_doctype: str) -> list[dict]:
	if not source_doctype or source_doctype in _ignored():
		return []
	definitions = [
		*_forward_links(source_doctype),
		*_forward_dynamic_links(source_doctype),
		*_child_links(source_doctype),
		*_incoming(source_doctype),
	]
	return _deduplicate(definitions)


def _forward_links(source_doctype) -> list[dict]:
	for field in frappe.get_meta(source_doctype).get_link_fields():
		if field.options in _ignored():
			continue
		yield {
			"name": field.fieldname,
			"label": _(field.label or field.fieldname),
			"cardinality": "one",
			"target_doctype": field.options,
			"kind": "link",
			"fieldname": field.fieldname,
			"derived": True,
		}


def _forward_dynamic_links(source_doctype) -> list[dict]:
	for field in frappe.get_meta(source_doctype).get_dynamic_link_fields():
		yield {
			"name": field.fieldname,
			"label": _(field.label or field.fieldname),
			"cardinality": "one",
			# Unknown until the record is loaded — the builder picks the target it expects.
			"target_doctype": None,
			"kind": "dynamic_link",
			"fieldname": field.fieldname,
			"doctype_fieldname": field.options,
			"derived": True,
		}


def _child_links(source_doctype) -> list[dict]:
	for table in frappe.get_meta(source_doctype).get_table_fields():
		for field in frappe.get_meta(table.options).get_link_fields():
			if field.options in _ignored():
				continue
			yield {
				"name": f"{table.fieldname}_{field.fieldname}",
				"label": _("{0} ({1})").format(
					_(field.label or field.fieldname), _(table.label or table.fieldname)
				),
				"cardinality": "many",
				"target_doctype": field.options,
				"kind": "child_link",
				"table_fieldname": table.fieldname,
				"fieldname": field.fieldname,
				"derived": True,
			}


def _incoming(source_doctype) -> list[dict]:
	"""Reverse Link edges only.

	Reverse Dynamic Links are deliberately left out. Which DocTypes a `reference_doctype` /
	`reference_name` pair points at is a fact about data, not schema — the framework's own
	discovery answers it with a query and caches the answer — so deriving them would make a
	relationship appear once some row happened to exist and be missing on a fresh site. Names
	are persisted in saved flows, so they have to be decided by the schema alone. Apps declare
	the dynamic references that matter to them.
	"""
	from frappe.desk.form.linked_with import get_linked_fields

	for doctype, link in (get_linked_fields(source_doctype) or {}).items():
		if not _is_queryable(doctype):
			continue
		for fieldname in link.get("fieldname") or []:
			yield _incoming_definition(doctype, fieldname, link.get("child_doctype"))


def _incoming_definition(doctype, fieldname, child_doctype) -> dict:
	return {
		"name": f"{frappe.scrub(doctype)}_via_{fieldname}",
		"label": _("{0} (by {1})").format(_(doctype), fieldname),
		"cardinality": "many",
		"target_doctype": doctype,
		"kind": "reverse_child_link" if child_doctype else "reverse_link",
		"fieldname": fieldname,
		"child_doctype": child_doctype,
		"derived": True,
	}


def _is_queryable(doctype) -> bool:
	"""Child, Single and virtual DocTypes can't be listed on their own."""
	if doctype in _ignored():
		return False
	meta = frappe.get_meta(doctype)
	return not (meta.istable or meta.issingle or meta.is_virtual)


@request_cache
def _ignored() -> set:
	"""Framework bookkeeping DocTypes, plus whatever apps add through the hook."""
	return IGNORED_DOCTYPES | set(frappe.get_hooks("automation_relationship_ignore") or [])


def _deduplicate(definitions) -> list[dict]:
	"""Two fields can scrub to the same name; keep the first and drop the ambiguous rest."""
	seen, kept = set(), []
	for definition in definitions:
		if definition["name"] in seen:
			continue
		seen.add(definition["name"])
		kept.append(definition)
	return kept


def _derived(source_doctype, relationship) -> dict:
	for definition in derived_definitions(source_doctype):
		if definition["name"] == relationship:
			return definition
	frappe.throw(_("Unknown derived relationship: {0}").format(relationship))


def _references(doctype, names) -> list[dict]:
	return [{"doctype": doctype, "name": name} for name in names if doctype and name]
