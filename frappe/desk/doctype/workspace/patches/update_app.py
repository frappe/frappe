# update app in `Module Def`

import frappe
from frappe.modules.utils import get_module_app


def execute():
	# The `Workspace` half of this patch is gone with `Workspace.app`: a workspace's app is its
	# module's app now, derived on read, so there is nothing left to backfill.
	for module in frappe.get_all("Module Def", ["name", "app_name"], filters=dict(custom=0)):
		if not module.app_name:
			try:
				frappe.db.set_value("Module Def", module.name, "app_name", get_module_app(module.name))
			except Exception:
				# for some default modules like Home, there is no folder / app
				pass
