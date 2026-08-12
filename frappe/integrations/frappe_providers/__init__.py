# imports - standard imports
# imports - module imports

def migrate_to():
	from frappe.integrations.frappe_providers.frappecloud import frappecloud_migrator

	return frappecloud_migrator()
