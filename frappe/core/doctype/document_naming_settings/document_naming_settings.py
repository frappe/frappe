# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from typing import List

import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import validate_series
from frappe.model.document import Document
from frappe.model.naming import get_naming_series_prefix, make_autoname
from frappe.permissions import get_doctypes_with_read
from frappe.utils import cint


class NamingSeriesNotSetError(frappe.ValidationError):
	pass


class DocumentNamingSettings(Document):
	@frappe.whitelist()
	def get_transactions_and_prefixes(self, arg=None):

		transactions = self._get_transactions()
		prefixes = self._get_prefixes(transactions)

		return {"transactions": transactions, "prefixes": prefixes}

	def _get_transactions(self) -> List[str]:

		readable_doctypes = set(get_doctypes_with_read())

		standard = frappe.get_all("DocField", {"fieldname": "naming_series"}, "parent", pluck="parent")
		custom = frappe.get_all("Custom Field", {"fieldname": "naming_series"}, "dt", pluck="dt")

		return sorted(readable_doctypes.intersection(standard + custom))

	def _get_prefixes(self, doctypes) -> List[str]:
		prefixes = ""
		for d in doctypes:
			options = ""
			try:
				options = self.get_options(d)
			except frappe.DoesNotExistError:
				frappe.msgprint(_("Unable to find DocType {0}").format(d))
				continue

			if options:
				prefixes = prefixes + "\n" + options
		prefixes.replace("\n\n", "\n")
		prefixes = prefixes.split("\n")

		custom_prefixes = frappe.get_all(
			"DocType",
			fields=["autoname"],
			filters={
				"name": ("not in", doctypes),
				"autoname": ("like", "%.#%"),
				"module": ("not in", ["Core"]),
			},
		)
		if custom_prefixes:
			prefixes = prefixes + [d.autoname.rsplit(".", 1)[0] for d in custom_prefixes]

		return sorted(set(prefixes))

	def get_options_list(self, options: str) -> List[str]:
		return [op.strip() for op in options.split("\n") if op.strip()]

	@frappe.whitelist()
	def update_series(self):
		"""update series list"""
		self.validate_series_set()
		self.check_duplicate()
		self.set_series_options_in_meta(self.transaction_type, self.naming_series_options)

		frappe.msgprint(
			_("Series Updated for {}").format(self.transaction_type), alert=True, indicator="green"
		)

	def validate_series_set(self):
		if self.transaction_type and not self.naming_series_options:
			frappe.throw(_("Please set the series to be used."))

	def set_series_options_in_meta(self, doctype: str, options: str) -> None:
		options = self.get_options_list(options)

		# validate names
		for i in options:
			self.validate_series_name(i)

		if options and self.user_must_always_select:
			options = [""] + options

		default = options[0] if options else ""

		option_string = "\n".join(options)

		self.update_naming_series_property_setter(doctype, "options", option_string)
		self.update_naming_series_property_setter(doctype, "default", default)

		self.naming_series_options = option_string

		frappe.clear_cache(doctype=doctype)

	def update_naming_series_property_setter(self, doctype, property, value):
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		make_property_setter(doctype, "naming_series", property, value, "Text")

	def check_duplicate(self):
		parent = list(
			set(
				frappe.db.sql_list(
					"""select dt.name
				from `tabDocField` df, `tabDocType` dt
				where dt.name = df.parent and df.fieldname='naming_series' and dt.name != %s""",
					self.transaction_type,
				)
				+ frappe.db.sql_list(
					"""select dt.name
				from `tabCustom Field` df, `tabDocType` dt
				where dt.name = df.dt and df.fieldname='naming_series' and dt.name != %s""",
					self.transaction_type,
				)
			)
		)
		sr = [[frappe.get_meta(p).get_field("naming_series").options, p] for p in parent]
		dt = frappe.get_doc("DocType", self.transaction_type)
		options = self.get_options_list(self.naming_series_options)
		for series in options:
			validate_series(dt, series)
			for i in sr:
				if i[0]:
					existing_series = [d.split(".")[0] for d in i[0].split("\n")]
					if series.split(".")[0] in existing_series:
						frappe.throw(_("Series {0} already used in {1}").format(series, i[1]))

	def validate_series_name(self, n):
		import re

		if not re.match(r"^[\w\- \/.#{}]+$", n, re.UNICODE):
			frappe.throw(
				_('Special Characters except "-", "#", ".", "/", "{" and "}" not allowed in naming series')
			)

	@frappe.whitelist()
	def get_options(self, doctype=None):
		doctype = doctype or self.transaction_type
		if not doctype:
			return

		if frappe.get_meta(doctype or self.transaction_type).get_field("naming_series"):
			return frappe.get_meta(doctype or self.transaction_type).get_field("naming_series").options

	@frappe.whitelist()
	def get_current(self):
		"""get series current"""
		if self.prefix:
			prefix = get_naming_series_prefix(self.prefix)
			self.current_value = frappe.db.get_value("Series", prefix, "current", order_by="name")

	@frappe.whitelist()
	def update_series_start(self):
		if not self.prefix:
			frappe.throw(_("Please select prefix first"))

		series = frappe.qb.DocType("Series")

		db_prefix = get_naming_series_prefix(self.prefix)

		if frappe.db.get_value("Series", db_prefix, "name", order_by="name") is None:
			series.insert(db_prefix, 0).columns(series.name, series.current).run()

		(
			frappe.qb.update(series)
			.set(series.current, cint(self.current_value))
			.where(series.name == db_prefix)
		).run()

		frappe.msgprint(
			_("Series counter for {} updated to {} successfully").format(self.prefix, self.current_value),
			alert=True,
			indicator="green",
		)

	@frappe.whitelist()
	def preview_series(self) -> str:
		"""Preview what the naming series will generate."""

		generated_names = []
		series = self.try_naming_series
		if not series:
			return ""

		try:
			doc = self._fetch_last_doc_if_available()
			for _count in range(3):
				generated_names.append(make_autoname(series, doc=doc))
		except Exception as e:
			if frappe.message_log:
				frappe.message_log.pop()
			return _("Failed to generate names from the series") + f"\n{str(e)}"

		# Explcitly rollback in case any changes were made to series table.
		frappe.db.rollback()  # nosemgrep
		return "\n".join(generated_names)

	def _fetch_last_doc_if_available(self):
		"""Fetch last doc for evaluating naming series with fields."""
		try:
			return frappe.get_last_doc(self.transaction_type)
		except Exception:
			return None
