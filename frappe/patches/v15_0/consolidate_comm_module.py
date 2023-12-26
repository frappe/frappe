import frappe


def execute():
	module = frappe.new_doc("Module Def")
	module.module_name = "Communications"
	module.app_name = "frappe"
	module.insert()
	frappe.set_value("DocType", "Communication", "module", "Communications")
	frappe.set_value("DocType", "Communication Link", "module", "Communications")
	frappe.set_value("DocType", "Notification", "module", "Communications")
	frappe.set_value("DocType", "Notification Recipient", "module", "Communications")
	frappe.set_value("DocType", "Comment", "module", "Desk")
	frappe.set_value("DocType", "Slack Webhook URL", "module", "Communications")
	frappe.set_value("DocType", "SMS Settings", "module", "Communications")
	frappe.set_value("DocType", "SMS Parameter", "module", "Communications")
	if frappe.db.exists("DocType", "SMS Log"):  # not yet in v13
		frappe.set_value("DocType", "SMS Log", "module", "Communications")
