# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.custom.doctype.customize_form.customize_form import CustomizeForm
from frappe.model import NO_VALUE_FIELDS
from frappe.model.document import Document
from frappe.utils import cint


class GlobalSearchSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.global_search_doctype.global_search_doctype import GlobalSearchDocType
		from frappe.types import DF

		allowed_in_global_search: DF.Table[GlobalSearchDocType]
	# end: auto-generated types

	def validate(self):
		dts, core_dts, repeated_dts = [], [], []

		for dt in self.allowed_in_global_search:
			if dt.document_type in dts:
				repeated_dts.append(dt.document_type)

			if frappe.get_meta(dt.document_type).module == "Core":
				core_dts.append(dt.document_type)

			dts.append(dt.document_type)

		if core_dts:
			core_dts = ", ".join(frappe.bold(dt) for dt in core_dts)
			frappe.throw(_("Core Modules {0} cannot be searched in Global Search.").format(core_dts))

		if repeated_dts:
			repeated_dts = ", ".join([frappe.bold(dt) for dt in repeated_dts])
			frappe.throw(_("Document Type {0} has been repeated.").format(repeated_dts))

		# reset cache
		frappe.cache.hdel("global_search", "search_priorities")


def get_doctypes_for_global_search():
	def get_from_db():
		doctypes = frappe.get_all("Global Search DocType", fields=["document_type"], order_by="idx ASC")
		return [d.document_type for d in doctypes] or []

	return frappe.cache.hget("global_search", "search_priorities", get_from_db)


@frappe.whitelist()
def reset_global_search_settings_doctypes():
	update_global_search_doctypes()


def update_global_search_doctypes():
	global_search_doctypes = []
	show_message(1, _("Fetching default Global Search documents."))

	installed_apps = [app for app in frappe.get_installed_apps() if app]
	active_domains = [domain for domain in frappe.get_active_domains() if domain]
	active_domains.append("Default")

	for app in installed_apps:
		search_doctypes = frappe.get_hooks(hook="global_search_doctypes", app_name=app)
		if not search_doctypes:
			continue

		for domain in active_domains:
			if search_doctypes.get(domain):
				global_search_doctypes.extend(search_doctypes.get(domain))

	doctype_list = {dt.name for dt in frappe.get_all("DocType")}
	allowed_in_global_search = []

	for dt in global_search_doctypes:
		if dt.get("index") is not None:
			allowed_in_global_search.insert(dt.get("index"), dt.get("doctype"))
			continue

		allowed_in_global_search.append(dt.get("doctype"))

	show_message(2, _("Setting up Global Search documents."))
	global_search_settings = frappe.get_single("Global Search Settings")
	global_search_settings.allowed_in_global_search = []
	for dt in allowed_in_global_search:
		if dt not in doctype_list:
			continue

		global_search_settings.append("allowed_in_global_search", {"document_type": dt})
	global_search_settings.save(ignore_permissions=True)
	show_message(3, "Global Search Documents have been reset.")


def show_message(progress, msg):
	frappe.publish_realtime(
		"global_search_settings",
		{"progress": progress, "total": 3, "msg": msg},
		user=frappe.session.user,
	)


def _eligible_global_search_docfields(meta):
	for df in sorted(meta.fields, key=lambda x: x.idx or 0):
		if df.fieldtype in NO_VALUE_FIELDS:
			continue
		if getattr(df, "hidden", False):
			continue
		if getattr(df, "is_virtual", False):
			continue
		yield df


@frappe.whitelist()
def get_global_search_field_options(doctype: str | None = None):
	if not doctype:
		frappe.throw(_("Document Type is required"))

	frappe.only_for("System Manager")

	meta = frappe.get_meta(doctype)

	options = [
		{
			"label": _("Document Name (ID)"),
			"value": "name",
			"checked": bool(getattr(meta, "show_name_in_global_search", False)),
			"is_system_generated": bool(getattr(meta, "show_name_in_global_search", False)),
		}
	]

	for df in _eligible_global_search_docfields(meta):
		is_system_generated = check_is_system_generated_property_setter(df)

		options.append(
			{
				"label": _(df.label, context=df.parent),
				"value": df.fieldname,
				"checked": bool(df.in_global_search),
				"is_system_generated": is_system_generated,
			}
		)

	# get default global search fields
	default_global_search_fields = get_all_default_global_search_fields(doctype)

	return {"options": options, "default_global_search_fields": default_global_search_fields}


def _customize_form_stub(doctype: str) -> CustomizeForm:
	"""In-memory Customize Form — same PS helpers as desk Customize Form."""
	cf = frappe.new_doc("Customize Form")
	cf.doc_type = doctype
	return cf


def get_all_default_global_search_fields(doctype: str) -> list[str]:
	"""Which fields would search-index by **schema + system PS only** (ignore Customize Form / non-system PS)."""
	meta = frappe.get_meta(doctype)
	cf = _customize_form_stub(doctype)

	# Layer 1: shipped DocField / DocType / Custom Field rows (Customize Form does not rewrite these).
	field_on = {
		df.fieldname: cint(cf.get_existing_property_value("in_global_search", df.fieldname) or 0)
		for df in (frappe.get_doc("DocType", doctype).fields or [])
	}
	for row in frappe.get_all(
		"Custom Field",
		filters={"dt": doctype},
		fields=["fieldname", "in_global_search"],
	):
		field_on[row.fieldname] = cint(row.in_global_search)

	include_name = cint(cf.get_existing_property_value("show_name_in_global_search") or 0)

	# Layer 2: app/system patches only (`is_system_generated` PS).
	for ps in frappe.get_all(
		"Property Setter",
		filters={
			"doc_type": doctype,
			"property": ("in", ("in_global_search", "show_name_in_global_search")),
			"is_system_generated": 1,
		},
		fields=["doctype_or_field", "field_name", "property", "value"],
		order_by="modified asc",
	):
		val = cint(ps.value)
		if ps.doctype_or_field == "DocType" and ps.property == "show_name_in_global_search":
			include_name = val
		elif ps.doctype_or_field == "DocField" and ps.property == "in_global_search" and ps.field_name:
			field_on[ps.field_name] = val

	out = ["name"] if include_name else []
	out.extend(df.fieldname for df in _eligible_global_search_docfields(meta) if field_on.get(df.fieldname))
	return out


def check_is_system_generated_property_setter(df):
	# Check if df.in_global_search is true or not if false directly return false
	# If True is that exist in property setter as is_system_generated is False and value is 1 then return False else True
	# Why is_system_generated False we are checking the point is few fields which are true are directly the doctype property those will not be in property setter as it is system generated

	if not df.in_global_search:
		return False

	property_setter = frappe.db.exists(
		"Property Setter",
		{
			"doc_type": df.parent,
			"field_name": df.fieldname,
			"property": "in_global_search",
			"is_system_generated": False,
			"value": 1,
		},
	)
	return False if property_setter else True


@frappe.whitelist()
def update_global_search_fields(doctype: str, fields: str):
	"""Apply global-search field selection via the same Property Setter path as Customize Form."""
	frappe.only_for("System Manager")
	if not doctype:
		frappe.throw(_("Document Type is required"))
	if frappe.get_meta(doctype).module == "Core":
		frappe.throw(_("Cannot configure Core DocTypes for Global Search."))

	fields = frappe.parse_json(fields)
	meta = frappe.get_meta(doctype)

	all_global_search_fields = [
		df.fieldname for df in _eligible_global_search_docfields(meta) if df.in_global_search
	]
	if bool(getattr(meta, "show_name_in_global_search", False)):
		all_global_search_fields.append("name")

	fields_to_add = [field for field in fields if field not in all_global_search_fields]
	fields_to_remove = [field for field in all_global_search_fields if field not in fields]

	cf = _customize_form_stub(doctype)
	for field in fields_to_add:
		if field == "name":
			cf.make_property_setter("show_name_in_global_search", 1, "Check")
		else:
			cf.make_property_setter("in_global_search", 1, "Check", fieldname=field)
	for field in fields_to_remove:
		if field == "name":
			cf.make_property_setter("show_name_in_global_search", 0, "Check")
		else:
			cf.make_property_setter("in_global_search", 0, "Check", fieldname=field)

	frappe.clear_cache(doctype=doctype)
	frappe.enqueue(
		"frappe.utils.global_search.rebuild_for_doctype",
		doctype=doctype,
		enqueue_after_commit=True,
	)

	return {"success": True}
