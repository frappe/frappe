# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	return get_columns(), get_data()


def get_columns():
	values_field_type = "Data"  # TODO: better text wrapping in reportview
	columns = [
		{"label": "Hook name", "fieldname": "hook_name", "fieldtype": "Data", "width": 200},
		{"label": "Hook key (optional)", "fieldname": "hook_key", "fieldtype": "Data", "width": 200},
		{"label": "Hook Values (resolved)", "fieldname": "hook_values", "fieldtype": values_field_type},
	]

	# Each app is shown in order as a column
	installed_apps = frappe.get_installed_apps(_ensure_on_bench=True)
	columns += [{"label": app, "fieldname": app, "fieldtype": values_field_type} for app in installed_apps]

	return columns


def get_data():
	hooks = frappe.get_hooks()
	installed_apps = frappe.get_installed_apps(_ensure_on_bench=True)

	def fmt_hook_values(v):
		"""Improve readability by discarding falsy values and removing containers when only 1
		value is in container"""
		if not v:
			return ""

		v = delist(v)

		if isinstance(v, dict | list):
			try:
				return frappe.as_json(v)
			except Exception:
				pass

		return str(v)

	data = []
	for hook, values in hooks.items():
		if isinstance(values, dict):
			for k, v in values.items():
				row = {"hook_name": hook, "hook_key": fmt_hook_values(k), "hook_values": fmt_hook_values(v)}
				for app in installed_apps:
					if app_hooks := delist(frappe.get_hooks(hook, app_name=app)):
						row[app] = fmt_hook_values(app_hooks.get(k))
				data.append(row)
		else:
			row = {"hook_name": hook, "hook_values": fmt_hook_values(values)}
			for app in installed_apps:
				row[app] = fmt_hook_values(frappe.get_hooks(hook, app_name=app))

			data.append(row)

	return data


def delist(val):
	if isinstance(val, list) and len(val) == 1:
		return val[0]
	return val
