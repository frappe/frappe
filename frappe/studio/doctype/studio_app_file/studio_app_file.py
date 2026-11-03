# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.studio.files import (
	is_export_folder,
	normalize_path,
	validate_allowed_extension,
	validate_editable,
)
from frappe.studio.realtime import publish_doc_change


class StudioAppFile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		content: DF.Code | None
		file_path: DF.Data
		is_folder: DF.Check
		studio_app: DF.Link
	# end: auto-generated types

	def validate(self):
		self.file_path = normalize_path(self.file_path)
		if self.is_folder:
			self.content = None
			if is_export_folder(self.file_path):
				frappe.throw(_("{0} is managed by Studio and can't be created.").format(self.file_path))
		else:
			validate_allowed_extension(self.file_path)
			validate_editable(self.studio_app, self.file_path)
		self.validate_unique_path()

	def validate_unique_path(self):
		duplicate = frappe.db.exists(
			"Studio App File",
			{"studio_app": self.studio_app, "file_path": self.file_path, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(_("{0} already exists in app {1}.").format(self.file_path, self.studio_app))

	def on_update(self):
		# the file path, not the docname, tells the editor and the renderer what to refresh
		publish_doc_change("Studio App File", self.file_path, self.studio_app)

	def after_delete(self):
		publish_doc_change("Studio App File", self.file_path, self.studio_app)


def on_doctype_update():
	# validate_unique_path is a check followed by an insert, so two concurrent requests both pass
	# it. The index is what makes one of them fail.
	frappe.db.add_unique(
		"Studio App File", ("studio_app", "file_path"), constraint_name="unique_app_file_path"
	)
