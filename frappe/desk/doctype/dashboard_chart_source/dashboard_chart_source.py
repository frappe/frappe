# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

<<<<<<< HEAD
import os

import frappe
=======
import shutil
from pathlib import Path

import frappe
from frappe import _
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
from frappe.model.document import Document
from frappe.modules import get_module_path, scrub
from frappe.modules.export_file import export_to_files

<<<<<<< HEAD

@frappe.whitelist()
def get_config(name):
	doc = frappe.get_doc("Dashboard Chart Source", name)
	with open(
		os.path.join(
			get_module_path(doc.module), "dashboard_chart_source", scrub(doc.name), scrub(doc.name) + ".js"
		),
	) as f:
		return f.read()
=======
FOLDER_NAME = "dashboard_chart_source"


@frappe.whitelist()
def get_config(name: str) -> str:
	doc: DashboardChartSource = frappe.get_doc("Dashboard Chart Source", name)
	return doc.read_config()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)


class DashboardChartSource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		module: DF.Link
		source_name: DF.Data
		timeseries: DF.Check
<<<<<<< HEAD

	# end: auto-generated types
	def on_update(self):
		export_to_files(record_list=[[self.doctype, self.name]], record_module=self.module, create_init=True)
=======
	# end: auto-generated types

	def on_update(self):
		if not frappe.request:
			return

		if not frappe.conf.developer_mode:
			frappe.throw(_("Creation of this document is only permitted in developer mode."))

		export_to_files(record_list=[[self.doctype, self.name]], record_module=self.module, create_init=True)

	def on_trash(self):
		if not frappe.conf.developer_mode and not frappe.flags.in_migrate:
			frappe.throw(_("Deletion of this document is only permitted in developer mode."))

		frappe.db.after_commit.add(self.delete_folder)

	def read_config(self) -> str:
		"""Return the config JS file for this dashboard chart source."""
		config_path = self.get_folder_path() / f"{scrub(self.name)}.js"
		return config_path.read_text() if config_path.exists() else ""

	def delete_folder(self):
		"""Delete the folder for this dashboard chart source."""
		path = self.get_folder_path()
		if path.exists():
			shutil.rmtree(path, ignore_errors=True)

	def get_folder_path(self) -> Path:
		"""Return the path of the folder for this dashboard chart source."""
		return Path(get_module_path(self.module)) / FOLDER_NAME / frappe.scrub(self.name)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
