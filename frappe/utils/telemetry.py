import frappe


def add_bootinfo(bootinfo):
	if not frappe.get_system_settings("enable_telemetry"):
		return

	bootinfo.posthog_host = frappe.conf.posthog_host
	bootinfo.posthog_project_id = frappe.conf.posthog_project_id
	bootinfo.enable_telemetry = True
