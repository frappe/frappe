# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.modules.utils import export_module_json

PYTHON_STARTER = """from frappe.desk.widgets import WidgetType


class __CLASS__(WidgetType):
	def get_data(self, filters=None):
		return {}
"""

ISLAND_STARTER = """import { defineWidget } from "@framework/ui/widget";

import Widget from "./__VUE_FILE__";

export const mount = defineWidget(Widget);
"""

VUE_STARTER = """<script setup>
import { useWidget } from "@framework/ui/widget";

const { widget, data } = useWidget();
</script>

<template>
	<div class="rounded-6 border border-outline-gray-1 p-4 text-base text-ink-gray-8">
		{{ widget.label }}
	</div>
</template>
"""


class WidgetType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.widget_type_field.widget_type_field import WidgetTypeField
		from frappe.desk.doctype.widget_type_size.widget_type_size import WidgetTypeSize
		from frappe.types import DF

		child_type: DF.Link | None
		fields: DF.Table[WidgetTypeField]
		island: DF.Data | None
		module: DF.Link
		sizes: DF.Table[WidgetTypeSize]
		type_name: DF.Data
	# end: auto-generated types

	def validate(self):
		sizes = [row.size for row in self.sizes]
		if len(sizes) != len(set(sizes)):
			frappe.throw(_("Each size can be listed only once."), title=_("Duplicate Size"))

	def on_update(self):
		from frappe.desk.widgets import clear_types_cache

		clear_types_cache()
		is_standard = not frappe.db.get_value("Module Def", self.module, "custom")
		if path := export_module_json(self, is_standard, self.module):
			self.write_starter_files(path)

	def on_trash(self):
		from frappe.desk.widgets import clear_types_cache

		clear_types_cache()

	def write_starter_files(self, path: str):
		"""The class and renderer a new type starts from. Files already there are kept."""
		name = os.path.basename(path)
		starters = {
			".py": PYTHON_STARTER.replace("__CLASS__", self.name.replace(" ", "").replace("-", "")),
			".island.js": ISLAND_STARTER.replace("__VUE_FILE__", f"{name}.vue"),
			".vue": VUE_STARTER,
		}
		for extension, content in starters.items():
			if not os.path.exists(path + extension):
				with open(path + extension, "w") as f:  # nosemgrep
					f.write(content)
