# imports - standard imports
# imports - module imports

from frappe.integrations.frappe_providers.frappecloud import frappecloud_migrator


def migrate_to():
	return frappecloud_migrator()
