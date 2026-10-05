import frappe


def execute():
	"""`read` became `read_records` and `read_file` became `read`; agents keep their tools."""
	if not frappe.db.exists("Flow Tool", "read_file"):
		return  # a new site, or already renamed
	# records first, so the freed name can take the file tool
	frappe.db.set_value("Flow Agent Tool", {"tool": "read"}, "tool", "read_records")
	frappe.db.set_value("Flow Agent Tool", {"tool": "read_file"}, "tool", "read")
	frappe.db.delete("Flow Tool", {"name": "read_file"})
