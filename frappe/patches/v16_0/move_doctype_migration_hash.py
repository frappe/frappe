import frappe
from frappe.core.doctype.migration_hash.migration_hash import set_migration_hash
from frappe.modules.import_file import get_file_path


def execute():
	"""Copy each DocType's hash to Migration Hash, so model sync keeps comparing DocTypes by hash."""
	frappe.reload_doc("core", "doctype", "migration_hash")
	if not frappe.db.has_column("DocType", "migration_hash"):
		return

	for row in get_hashed_doctypes():
		if frappe.scrub(row.module) in frappe.local.module_app:
			set_migration_hash(get_file_path(row.module, "DocType", row.name), row.migration_hash)


def get_hashed_doctypes():
	doctype = frappe.qb.DocType("DocType")
	return (
		frappe.qb.from_(doctype)
		.select(doctype.name, doctype.module, doctype.migration_hash)
		.where(doctype.migration_hash.isnotnull() & (doctype.migration_hash != ""))
		.run(as_dict=True)
	)
