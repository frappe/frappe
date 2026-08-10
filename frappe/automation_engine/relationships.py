# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Safe, hook-driven record relationship discovery and resolution.

Applications register provider classes through the `automation_relationships` hook - a saved
workflow only ever names a relationship, never a callable - so configuration can't reach
arbitrary Python. Providers hand back `{doctype, name}` references, which are checked against
the declared target DocTypes and the current user's read permission before anything is loaded.
"""

import frappe
from frappe import _
from frappe.utils.caching import request_cache

MAX_RELATED_ROWS = 1000


class AutomationRelationshipProvider:
	def get_definitions(self, source_doctype: str) -> list[dict]:
		"""Return builder-safe relationship metadata for `source_doctype`."""
		raise NotImplementedError

	def resolve(self, source_doc, relationship: str, params: dict) -> list[dict]:
		"""Return zero or more {doctype, name} references."""
		raise NotImplementedError

	def query(self, source_doc, relationship: str, filters: list, limit: int) -> list[dict]:
		"""Override to push related-record filters into an application query.

		The fallback resolves every related reference first, so providers backing a `many`
		relationship over a large table should implement this themselves.
		"""
		return _query_resolved(self, source_doc, relationship, filters, limit)


def get_relationship_definitions(source_doctype: str | None) -> list[dict]:
	"""Return the builder-visible relationships available on `source_doctype`."""
	return [_public(definition) for definition in _definitions(source_doctype)]


def get_relationship_definition(source_doctype: str, relationship: str) -> dict:
	return _public(_definition(source_doctype, relationship))


def get_relationship_targets(source_doctype: str | None, relationships) -> dict[str, str | None]:
	"""Validate the flow's predeclared aliases and return {alias: target doctype}.

	`None` as a target means "not known until runtime" - the alias is usable, but actions
	can't validate their params against a DocType meta.
	"""
	targets = {"trigger": source_doctype}
	for item in _parse_relationships(relationships):
		_validate_alias(item, targets)
		definition = _definition(targets[item.get("source") or "trigger"], item["relationship"])
		if definition["cardinality"] != "one":
			frappe.throw(
				_("Relationship {0} cannot be used as a single record alias").format(item["relationship"])
			)
		targets[item["alias"]] = _configured_target(definition, item)
	return targets


def resolve_relationships(trigger_doc, relationships) -> dict[str, dict]:
	"""Resolve the predeclared aliases into record references for a run."""
	records = {"trigger": _reference(trigger_doc)} if trigger_doc else {}
	for item in _parse_relationships(relationships):
		source = load_record(records.get(item.get("source") or "trigger"))
		records[item["alias"]] = resolve_one(source, item["relationship"], item.get("params"))
	return records


def resolve_one(source_doc, relationship: str, params=None) -> dict:
	definition = _definition(source_doc.doctype, relationship)
	if definition["cardinality"] != "one":
		frappe.throw(_("Relationship {0} returns multiple records").format(relationship))
	name = _provider_name(definition, relationship)
	resolved = definition["provider"].resolve(source_doc, name, params or {}) or []
	if len(resolved) != 1:
		frappe.throw(_("Relationship {0} did not resolve to one record").format(relationship))
	return _permitted_reference(resolved[0], definition)


def query_related(source_doc, relationship: str, filters=None, limit=MAX_RELATED_ROWS) -> list[dict]:
	definition = _definition(source_doc.doctype, relationship)
	limit = min(frappe.utils.cint(limit) or MAX_RELATED_ROWS, MAX_RELATED_ROWS)
	name = _provider_name(definition, relationship)
	rows = definition["provider"].query(source_doc, name, filters or [], limit)
	return [_permitted_reference(row, definition) for row in rows or []]


def load_record(reference, permission_type=None):
	if not reference:
		frappe.throw(_("Record alias could not be resolved"))
	doc = frappe.get_doc(reference["doctype"], reference["name"])
	if permission_type:
		doc.check_permission(permission_type)
	return doc


@request_cache
def _providers() -> list:
	"""App providers first, then the schema provider - an app definition shadows a derived one."""
	from frappe.automation_engine.schema_relationships import SchemaRelationshipProvider

	providers = []
	for path in frappe.get_hooks("automation_relationships"):
		provider = frappe.get_attr(path)
		providers.append(provider() if isinstance(provider, type) else provider)
	providers.append(SchemaRelationshipProvider())
	return providers


def _definitions(source_doctype: str | None) -> list[dict]:
	"""Every validated definition registered for `source_doctype`."""
	if not source_doctype:
		return []
	definitions = {}
	for provider in _providers():
		for item in provider.get_definitions(source_doctype) or []:
			definition = _validated_definition(provider, source_doctype, item)
			_claim_name(definitions, definition, source_doctype)
	return list(definitions.values())


def _claim_name(definitions, definition, source_doctype):
	"""First provider to claim a name keeps it; two apps claiming one is a configuration error."""
	held = definitions.get(definition["name"])
	if held and not definition.get("derived"):
		frappe.throw(_("Duplicate automation relationship name on {0}").format(source_doctype))
	if not held:
		definitions[definition["name"]] = definition


def _definition(source_doctype: str | None, relationship: str | None) -> dict:
	for definition in _definitions(source_doctype):
		if definition["name"] == relationship:
			return definition
	frappe.throw(_("Unknown automation relationship: {0}").format(relationship))


def _validated_definition(provider, source_doctype, definition) -> dict:
	definition = _renamed(dict(definition), source_doctype)
	if not definition.get("name") or definition.get("cardinality") not in ("one", "many"):
		frappe.throw(_("Invalid automation relationship definition"))
	if definition.get("source_doctype") not in (None, source_doctype):
		frappe.throw(_("Relationship source DocType does not match"))
	definition["source_doctype"] = source_doctype
	definition.setdefault("provider", provider)
	return definition


def _renamed(definition, source_doctype) -> dict:
	"""`derived_from` gives a schema relationship a stable name and a readable label.

	The app supplies nothing but the two strings - resolution stays with the schema provider,
	so a rename can't drift from the field that backs it.
	"""
	source = definition.pop("derived_from", None)
	if not source:
		return definition
	definition["derived_name"] = source
	from frappe.automation_engine.schema_relationships import SchemaRelationshipProvider

	derived = dict(_schema_definition(source_doctype, source))
	derived["provider"] = SchemaRelationshipProvider()
	derived.pop("derived", None)
	return {**derived, **definition}


def _schema_definition(source_doctype, relationship) -> dict:
	from frappe.automation_engine.schema_relationships import derived_definitions

	for definition in derived_definitions(source_doctype):
		if definition["name"] == relationship:
			return definition
	frappe.throw(_("Unknown derived relationship: {0} on {1}").format(relationship, source_doctype))


INTERNAL_KEYS = (
	"provider",
	"kind",
	"fieldname",
	"table_fieldname",
	"child_doctype",
	"doctype_fieldname",
	"derived_name",
)


def _public(definition) -> dict:
	"""Drop the provider and its bookkeeping - definitions cross into API responses."""
	return {key: value for key, value in definition.items() if key not in INTERNAL_KEYS}


def _allowed_doctypes(definition) -> list:
	return definition.get("target_doctypes") or [definition["target_doctype"]]


def _configured_target(definition, item) -> str | None:
	target = item.get("target_doctype") or definition.get("target_doctype")
	allowed = definition.get("target_doctypes")
	if target and allowed and target not in allowed:
		frappe.throw(_("Relationship target DocType is not allowed"))
	return target


def _parse_relationships(relationships) -> list[dict]:
	if not relationships:
		return []
	parsed = frappe.parse_json(relationships) if isinstance(relationships, str) else relationships
	if not isinstance(parsed, list):
		frappe.throw(_("Relationships must be a JSON list"))
	return [dict(item) for item in parsed]


def _validate_alias(item, aliases):
	if not item.get("alias") or not item.get("relationship"):
		frappe.throw(_("Each relationship needs an alias and relationship name"))
	if item["alias"] in aliases:
		frappe.throw(_("Duplicate record alias: {0}").format(item["alias"]))
	if (item.get("source") or "trigger") not in aliases:
		frappe.throw(_("Unknown relationship source alias: {0}").format(item.get("source")))


def _provider_name(definition, relationship) -> str:
	"""A renamed relationship is still resolved under the derived name its provider knows."""
	return definition.get("derived_name") or relationship


def _reference(doc) -> dict:
	return {"doctype": doc.doctype, "name": doc.name}


def _permitted_reference(value, definition) -> dict:
	"""A provider is application code, but its output still has to clear the allow-list."""
	doctype, name = value.get("doctype"), value.get("name")
	allowed = _allowed_doctypes(definition)
	if not (doctype and name) or (any(allowed) and doctype not in allowed):
		frappe.throw(_("Relationship provider returned an invalid record reference"))
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("Related record does not exist: {0} {1}").format(doctype, name))
	frappe.has_permission(doctype, "read", doc=name, throw=True)
	return {"doctype": doctype, "name": name}


def _query_resolved(provider, source_doc, relationship, filters, limit):
	references = provider.resolve(source_doc, relationship, {}) or []
	if not references:
		return []
	doctypes = {item["doctype"] for item in references}
	if len(doctypes) != 1:
		frappe.throw(_("Filtered relationship queries require one target DocType"))
	target_doctype = doctypes.pop()
	names = frappe.get_list(
		target_doctype,
		filters=[["name", "in", [item["name"] for item in references]], *filters],
		pluck="name",
		limit=limit,
	)
	return [{"doctype": target_doctype, "name": name} for name in names]
