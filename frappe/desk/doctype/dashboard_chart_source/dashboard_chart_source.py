# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import shutil
from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.modules import get_module_path, scrub
from frappe.modules.export_file import export_to_files

FOLDER_NAME = "dashboard_chart_source"


@frappe.whitelist()
def get_config(name: str) -> str:
	module, name = frappe.get_value("Dashboard Chart Source", name, ["module", "name"])
	file = get_folder_path(module, name) / f"{scrub(name)}.js"
	return file.read_text()


class DashboardChartSource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		module: DF.Link
		source_name: DF.Data
		timeseries: DF.Check
	# end: auto-generated types

	def on_update(self):
		if not frappe.conf.developer_mode and not frappe.flags.in_migrate:
			frappe.throw(_("Creation of this document is only permitted in developer mode."))

		export_to_files(
			record_list=[[self.doctype, self.name]], record_module=self.module, create_init=True
		)

	def on_trash(self):
		if not frappe.conf.developer_mode and not frappe.flags.in_migrate:
			frappe.throw(_("Deletion of this document is only permitted in developer mode."))

		frappe.db.after_commit(self.delete_folder_with_contents)

	def delete_folder_with_contents(self):
		dir_path = get_folder_path(self.module, self.name)
		if dir_path.exists():
			shutil.rmtree(dir_path, ignore_errors=True)


def get_folder_path(module: str, name: str) -> Path:
	return Path(get_module_path(module)) / FOLDER_NAME / frappe.scrub(name)
