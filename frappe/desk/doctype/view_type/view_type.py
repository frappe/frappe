# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import functools
import importlib
import re
from types import ModuleType

import frappe
from frappe import _
from frappe.desk.doctype.navigation_item_type.navigation_item_type import SYSTEM_WRITE_FLAGS
from frappe.model.document import Document
from frappe.modules.utils import get_module_app

# Also in `global_cache_keys`, so `clear_cache` and every migrate drop it.
CACHE_KEY = "view_types"

# `/<doctype>/view/<type>` is the type's plain view, so its name lower-cased is a view key.
TYPE_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


class ViewType(Document):
	"""A way to draw a doctype's records, shipped by an app as a file beside its renderer; rows are code-owned."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		icon: DF.Data | None
		label: DF.Data
		module: DF.Link
	# end: auto-generated types

	def validate(self):
		self.validate_app_content()
		self.validate_type_name()

	def validate_app_content(self):
		"""Refuse writes outside developer mode or a system write; permissions miss Administrator."""
		if frappe.conf.developer_mode or any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			return

		frappe.throw(
			_(
				"{0} is contributed by an app and can only be authored in developer mode. "
				"An app adds a view type by shipping this record and its renderer together."
			).format(frappe.bold(self.name)),
			title=_("Not Editable"),
		)

	def validate_type_name(self):
		if not TYPE_NAME.fullmatch(self.name.lower()) or self.name.lower() == "record":
			frappe.throw(
				_(
					"{0} cannot name a view type: it must be letters, digits and dashes, and not Record."
				).format(frappe.bold(self.name)),
				title=_("Invalid Name"),
			)

	def on_update(self):
		clear_view_types()
		self.export_type()

	def on_trash(self):
		clear_view_types()

	def export_type(self):
		"""Write this type to `<module>/view_type/<scrubbed>/`, the walk that imports it at migrate."""
		from frappe.modules.export_file import export_to_files

		if frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_module=self.module)


def view_types() -> dict[str, frappe._dict]:
	"""`{name: {name, label, icon, module}}` of every view type, in the order they were made."""
	return frappe.cache.get_value(CACHE_KEY, generator=read_view_types)


def type_keys() -> dict[str, str]:
	"""`{"list": "List"}`: each type's plain view address segment, `/<doctype>/view/<key>`."""
	return {name.lower(): name for name in view_types()}


def applies_to(view_type: str, doctype: str) -> bool:
	"""Whether the type fits the doctype, by the type's `applies_to(meta)`; without one it fits every doctype."""
	check = getattr(rules(view_type), "applies_to", None)
	return bool(check(frappe.get_meta(doctype))) if check else True


def refuse_where_it_does_not_apply(view_type: str, doctype: str):
	if not applies_to(view_type, doctype):
		frappe.throw(
			_("{0} views don't apply to {1}.").format(_(view_types()[view_type].label), _(doctype)),
			title=_("Wrong View Type"),
		)


def validate_settings(view_type: str, doctype: str, settings: dict):
	"""The type's own check of its settings keys, which throws on a bad one."""
	if check := getattr(rules(view_type), "validate_settings", None):
		check(doctype, settings)


def rules(view_type: str) -> ModuleType | None:
	"""The type's optional `<scrubbed>.py` beside its record."""
	record = view_types().get(view_type)
	if not record:
		return None

	scrubbed = frappe.scrub(record.name)
	app = get_module_app(record.module)
	return rules_module(f"{app}.{frappe.scrub(record.module)}.view_type.{scrubbed}.{scrubbed}")


@functools.cache
def rules_module(path: str) -> ModuleType | None:
	try:
		return importlib.import_module(path)
	except ModuleNotFoundError as error:
		# Only the rules file itself may be missing; an import it makes that fails is a real error.
		if error.name and (path == error.name or path.startswith(f"{error.name}.")):
			return None
		raise


def read_view_types() -> dict[str, frappe._dict]:
	rows = frappe.get_all(
		"View Type", fields=["name", "label", "icon", "module"], order_by="creation asc, name asc"
	)
	return {row.name: row for row in rows}


def clear_view_types():
	# After commit too: a reader whose snapshot predates this write may refill the cache meanwhile.
	frappe.cache.delete_value(CACHE_KEY)
	frappe.db.after_commit.add(lambda: frappe.cache.delete_value(CACHE_KEY))
