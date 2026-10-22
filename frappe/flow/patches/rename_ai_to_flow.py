import frappe

DOCTYPE_RENAMES = {
	"AI Provider": "Flow Provider",
	"AI Model": "Flow Model",
	"AI Tool": "Flow Tool",
	"AI Agent": "Flow Agent",
	"AI Agent Tool": "Flow Agent Tool",
	"AI Agent Knowledge Base": "Flow Agent Knowledge Base",
	"AI Knowledge Base": "Flow Knowledge Base",
	"AI Knowledge Source": "Flow Knowledge Source",
	"AI Knowledge Chunk": "Flow Knowledge Chunk",
	"AI Knowledge Settings": "Flow Knowledge Settings",
	"AI Session": "Flow Session",
	"AI Session Message": "Flow Session Message",
	"AI Session Attachment": "Flow Session Attachment",
	"AI Run": "Flow Run",
	"AI Trigger": "Flow Trigger",
}


def execute():
	"""Rename the AI module and every AI doctype to Flow. Runs before model sync so the
	renamed JSON syncs onto the existing tables instead of creating empty duplicates."""
	if not frappe.db.exists("Module Def", "AI"):
		return

	# Renaming re-saves the doctypes; controllers are already on disk as flow_* while the DB
	# still holds the AI names, so the export would fail. in_import skips it (as model sync does).
	in_import = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		_rename_ai_to_flow()
	finally:
		frappe.flags.in_import = in_import


def _rename_ai_to_flow():
	# ORM blocks renaming non-custom modules, so do it via SQL.
	if not frappe.db.exists("Module Def", "Flow"):
		frappe.db.sql("update `tabModule Def` set name='Flow', module_name='Flow' where name='AI'")

	# Repoint every doctype to Flow before renaming: each rename re-saves linking siblings,
	# which validate the module link.
	frappe.db.sql("update `tabDocType` set module='Flow' where module='AI'")
	frappe.clear_cache()

	for old, new in DOCTYPE_RENAMES.items():
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)

	# Password fields (e.g. api_key) live in __Auth keyed by doctype name; the doctype
	# rename doesn't migrate them, so repoint them or every saved key reads as missing.
	for old, new in DOCTYPE_RENAMES.items():
		frappe.db.sql("update `__Auth` set doctype=%s where doctype=%s", (new, old))

	# Workspaces are pure JSON config; drop the old ones so sync recreates them as Flow.
	for ws in ("Workspace", "Workspace Sidebar"):
		if frappe.db.exists(ws, "AI"):
			frappe.delete_doc(ws, "AI", force=True, ignore_permissions=True)
