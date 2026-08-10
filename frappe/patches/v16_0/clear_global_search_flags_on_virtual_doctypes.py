import frappe


def execute():
	"""Clear global-search configuration from virtual doctypes.

	Virtual doctypes no longer participate in global search indexing (see
	frappe.utils.global_search.rebuild_for_doctype). Pre-existing sites may
	still carry the flags — retroactively clear them so DocType.validate()
	doesn't throw on the first save after upgrade, and clear any stale
	__global_search rows for those doctypes.
	"""
	virtual_doctypes = frappe.get_all("DocType", filters={"is_virtual": 1}, pluck="name")
	if not virtual_doctypes:
		print("clear_global_search_flags_on_virtual_doctypes: no virtual doctypes; skipping.")
		return

	print(
		f"clear_global_search_flags_on_virtual_doctypes: {len(virtual_doctypes)} virtual doctype(s) — "
		"clearing global-search flags and stale index rows."
	)

	_clear_doctype_flag(virtual_doctypes)
	_clear_docfield_flag(virtual_doctypes)
	_clear_custom_field_flag(virtual_doctypes)
	_delete_property_setters(virtual_doctypes)
	_delete_stale_index_rows(virtual_doctypes)
	_regenerate_settings_singleton()
	_bust_caches(virtual_doctypes)


def _clear_doctype_flag(virtual_doctypes):
	DocType = frappe.qb.DocType("DocType")
	query = (
		frappe.qb.from_(DocType)
		.select(DocType.name)
		.where(DocType.name.isin(virtual_doctypes))
		.where(DocType.show_name_in_global_search == 1)
	)
	affected = [row[0] for row in query.run()]
	if not affected:
		print("  DocType.show_name_in_global_search: 0 rows affected.")
		return

	(
		frappe.qb.update(DocType)
		.set(DocType.show_name_in_global_search, 0)
		.where(DocType.name.isin(affected))
		.run()
	)
	print(f"  DocType.show_name_in_global_search: cleared on {len(affected)} doctype(s).")


def _clear_docfield_flag(virtual_doctypes):
	DocField = frappe.qb.DocType("DocField")
	query = (
		frappe.qb.from_(DocField)
		.select(DocField.parent, DocField.fieldname)
		.where(DocField.parent.isin(virtual_doctypes))
		.where(DocField.in_global_search == 1)
	)
	affected = query.run(as_dict=True)
	if not affected:
		print("  DocField.in_global_search: 0 rows affected.")
		return

	(
		frappe.qb.update(DocField)
		.set(DocField.in_global_search, 0)
		.where(DocField.parent.isin(virtual_doctypes))
		.where(DocField.in_global_search == 1)
		.run()
	)
	print(f"  DocField.in_global_search: cleared on {len(affected)} field(s).")


def _clear_custom_field_flag(virtual_doctypes):
	# Custom Field carries an independent copy of in_global_search when a
	# field was added post-hoc via Customize Form's field-adder flow.
	CustomField = frappe.qb.DocType("Custom Field")
	query = (
		frappe.qb.from_(CustomField)
		.select(CustomField.dt, CustomField.fieldname)
		.where(CustomField.dt.isin(virtual_doctypes))
		.where(CustomField.in_global_search == 1)
	)
	affected = query.run(as_dict=True)
	if not affected:
		print("  Custom Field.in_global_search: 0 rows affected.")
		return

	(
		frappe.qb.update(CustomField)
		.set(CustomField.in_global_search, 0)
		.where(CustomField.dt.isin(virtual_doctypes))
		.where(CustomField.in_global_search == 1)
		.run()
	)
	print(f"  Custom Field.in_global_search: cleared on {len(affected)} custom field(s).")


def _delete_property_setters(virtual_doctypes):
	# Customize Form toggles global-search flags as Property Setter rows,
	# not by mutating DocField directly. Wipe those too.
	PS = frappe.qb.DocType("Property Setter")
	query = (
		frappe.qb.from_(PS)
		.select(PS.name)
		.where(PS.doc_type.isin(virtual_doctypes))
		.where(PS.property.isin(["in_global_search", "show_name_in_global_search"]))
	)
	affected = [row[0] for row in query.run()]
	if not affected:
		print("  Property Setter: 0 rows affected.")
		return

	frappe.qb.from_(PS).delete().where(PS.name.isin(affected)).run()
	print(f"  Property Setter: deleted {len(affected)} row(s).")


def _delete_stale_index_rows(virtual_doctypes):
	# Rows may have been inserted before this fix or during partial-indexing
	# runs. Clean up so search doesn't surface entries for doctypes that no
	# longer participate.
	if "__global_search" not in frappe.db.get_tables():
		print("  __global_search: table not present; skipping.")
		return

	GlobalSearch = frappe.qb.Table("__global_search")
	count_query = (
		frappe.qb.from_(GlobalSearch)
		.select(GlobalSearch.doctype)
		.where(GlobalSearch.doctype.isin(virtual_doctypes))
	)
	affected = count_query.run()
	if not affected:
		print("  __global_search: 0 stale rows.")
		return

	frappe.qb.from_(GlobalSearch).delete().where(GlobalSearch.doctype.isin(virtual_doctypes)).run()
	print(f"  __global_search: deleted {len(affected)} stale row(s).")


def _regenerate_settings_singleton():
	# With Guard A in place, this call filters virtual doctypes out during
	# regeneration. Idempotent — safe to run on every upgrade.
	from frappe.desk.doctype.global_search_settings.global_search_settings import (
		update_global_search_doctypes,
	)

	update_global_search_doctypes()
	print("  Global Search Settings: allowed_in_global_search regenerated (virtual doctypes filtered).")


def _bust_caches(virtual_doctypes):
	# Targeted invalidation instead of a full frappe.clear_cache() — cheaper
	# and less noisy on large sites.
	frappe.cache.hdel("global_search", "search_priorities")
	frappe.cache.delete_value("doctypes_with_global_search")
	for dt in virtual_doctypes:
		frappe.clear_cache(doctype=dt)
	print("  Caches: search_priorities, doctypes_with_global_search, per-doctype meta invalidated.")
