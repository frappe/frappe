import glob
import json
import os

import frappe
from frappe.query_builder import DocType as _DocType


def execute():
	"""Resetting creation datetimes for DocTypes"""
	DocType = _DocType("DocType")
	doctype_jsons = glob.glob(
		os.path.join("..", "apps", "frappe", "frappe", "**", "doctype", "**", "*.json")
	)

	frappe_modules = frappe.get_all("Module Def", filters={"app_name": "frappe"}, pluck="name")
	site_doctypes = frappe.get_all(
		"DocType",
		filters={"module": ("in", frappe_modules), "custom": False},
		fields=["name", "creation"],
	)

	for dt_path in doctype_jsons:
		with open(dt_path) as f:
			try:
				file_schema = frappe._dict(json.load(f))
			except Exception:
				continue

			if not file_schema.name:
				continue

			_site_schema = [x for x in site_doctypes if x.name == file_schema.name]
			if not _site_schema:
				continue

			if file_schema.creation != _site_schema[0].creation:
				frappe.qb.update(DocType).set(DocType.creation, file_schema.creation).where(
					DocType.name == file_schema.name
				).run()
