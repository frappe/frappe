

def migrate_to(local_site, frappe_provider):
	if frappe_provider in ("frappe.cloud", "frappecloud.com"):
		from frappe.integrations.frappe_providers.frappecloud import frappecloud_migrator
		return frappecloud_migrator(local_site)
	else:
		import sys
		print("{} is not supported yet".format(frappe_provider))
		sys.exit(1)