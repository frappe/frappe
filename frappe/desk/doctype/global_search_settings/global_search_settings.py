# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.custom.doctype.customize_form.customize_form import CustomizeForm
from frappe.model import NO_VALUE_FIELDS
from frappe.model.document import Document


class GlobalSearchSettings(Document):
	_DOCTYPE_NAME = "Global Search Settings"

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
	"""
	Get the global search field options which is list of fields with checked status if that field is in global search
	and name is also included if show_name_in_global_search is set
	"""
	if not doctype:
		frappe.throw(_("Document Type is required"))

	frappe.only_for("System Manager")

	meta = frappe.get_meta(doctype)

	options = [
		{
			"label": _("Document Name (ID)"),
			"value": "name",
			"checked": bool(getattr(meta, "show_name_in_global_search", False)),
		}
	]

	for df in _eligible_global_search_docfields(meta):
		options.append(
			{
				"label": _(df.label, context=df.parent),
				"value": df.fieldname,
				"checked": bool(df.in_global_search),
			}
		)

	return options


def _customize_form_stub(doctype: str) -> CustomizeForm:
	"""In-memory Customize Form — same PS helpers as desk Customize Form."""
	cf = frappe.new_doc("Customize Form")
	cf.doc_type = doctype
	return cf


def _set_global_search_property_setter(cf: CustomizeForm, fieldname: str, enabled: bool) -> None:
	"""Toggle DocType / DocField flags via `CustomizeForm.make_property_setter` (same as Customize Form desk save)."""
	val = 1 if enabled else 0
	if fieldname == "name":
		cf.make_property_setter("show_name_in_global_search", val, "Check")
	else:
		cf.make_property_setter("in_global_search", val, "Check", fieldname=fieldname)


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

	# Current set of global search fields which are in the database
	current = {df.fieldname for df in _eligible_global_search_docfields(meta) if df.in_global_search}
	if bool(getattr(meta, "show_name_in_global_search", False)):
		current.add("name")

	# Desired set of global search fields which are in the request
	desired = set(fields)

	# So basically we need to add the fields that are in the request and are not in the database
	# and remove the fields that are in the database and are not in the request

	# Create a Customize Form stub to apply property setters
	cf = _customize_form_stub(doctype)

	# Add the fields that are in the request and are not in the database
	for fieldname in desired - current:
		_set_global_search_property_setter(cf, fieldname, True)

	# Remove the fields that are in the database and are not in the request
	for fieldname in current - desired:
		_set_global_search_property_setter(cf, fieldname, False)

	# Clear the cache and enqueue the rebuild for the doctype
	frappe.clear_cache(doctype=doctype)
	frappe.enqueue(
		"frappe.utils.global_search.rebuild_for_doctype",
		doctype=doctype,
		enqueue_after_commit=True,
	)

	return {"success": True}
