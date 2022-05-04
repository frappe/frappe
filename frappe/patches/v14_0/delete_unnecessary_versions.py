import frappe

# ref: https://github.com/frappe/frappe/pull/14558
VERSIONS_TO_DELETE = [
	"Activity Log",
	"Error Log",
	"Error Snapshot",
	"Energy Point Log",
	"Notification Log",
	"Route History",
	"Scheduled Job Log",
	"View Log",
	"Web Page View",
]


def execute():
	"""Some log-like doctypes had track changes enabled, these version logs
	are empty but consume space. This patch removes such version logs.
	"""
	for doctype in VERSIONS_TO_DELETE:
		if not frappe.get_meta(doctype).track_changes:
			frappe.db.delete("Version", {"ref_doctype": doctype})
			frappe.db.commit()
