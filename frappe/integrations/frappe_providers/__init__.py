# imports - standard imports
import sys

# imports - module imports
from frappe.integrations.frappe_providers.frappecloud import frappecloud_migrator


def migrate_to(local_site, frappe_provider):
	if frappe_provider in ("frappe.cloud", "frappecloud.com"):
<<<<<<< HEAD
		return frappecloud_migrator(local_site)
=======
		return frappecloud_migrator(local_site, frappe_provider)
>>>>>>> e384c826dcc54f2b1f4e697e2dace3e05c849d3a
	else:
		print("{} is not supported yet".format(frappe_provider))
		sys.exit(1)
