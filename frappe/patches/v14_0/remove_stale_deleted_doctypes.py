import frappe
from frappe.model.base_document import get_controller

DELETED_DOCTYPES = [
	"Feedback",
	"Test rename new",
	"test",
	"Scheduler Log",
]


def execute():
	for doctype in DELETED_DOCTYPES:
		if not controller_exists(doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True)


def controller_exists(doctype: str) -> bool:
	try:
		get_controller(doctype)
		return True  # Another controller exists for this doctype, perhaps a separate app?
	except Exception:
		return False
