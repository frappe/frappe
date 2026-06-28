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

	# Rename the module via SQL: the ORM blocks renaming non-custom modules and would
	# trigger developer-mode folder side effects.
	if not frappe.db.exists("Module Def", "Flow"):
		frappe.db.sql("update `tabModule Def` set name='Flow', module_name='Flow' where name='AI'")

	# Repoint every AI doctype to Flow first. Renaming one doctype re-saves the siblings
	# that link to it, and those saves validate the module link — so the module must be
	# valid on all of them before the rename loop runs.
	frappe.db.sql("update `tabDocType` set module='Flow' where module='AI'")
	frappe.clear_cache()

	for old, new in DOCTYPE_RENAMES.items():
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)

	# Workspaces are pure JSON config; drop the old ones so sync recreates them as Flow.
	for ws in ("Workspace", "Workspace Sidebar"):
		if frappe.db.exists(ws, "AI"):
			frappe.delete_doc(ws, "AI", force=True, ignore_permissions=True)
