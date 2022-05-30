# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from typing import List

import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import validate_series
from frappe.model.document import Document
from frappe.model.naming import make_autoname, parse_naming_series
from frappe.permissions import get_doctypes_with_read
from frappe.utils import cint, cstr


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

		# update in property setter
		prop_dict = {"options": "\n".join(options), "default": default}

		for prop in prop_dict:
			ps_exists = frappe.db.get_value(
				"Property Setter", {"field_name": "naming_series", "doc_type": doctype, "property": prop}
			)

			if ps_exists:
				ps = frappe.get_doc("Property Setter", ps_exists)
				ps.value = prop_dict[prop]
				ps.save()
			else:
				ps = frappe.get_doc(
					{
						"doctype": "Property Setter",
						"doctype_or_field": "DocField",
						"doc_type": doctype,
						"field_name": "naming_series",
						"property": prop,
						"value": prop_dict[prop],
						"property_type": "Text",
						"__islocal": 1,
					}
				)
				ps.save()

		self.naming_series_options = "\n".join(options)

		frappe.clear_cache(doctype=doctype)

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
	def get_current(self, arg=None):
		"""get series current"""
		if self.prefix:
			prefix = self.parse_naming_series()
			self.current_value = frappe.db.get_value("Series", prefix, "current", order_by="name")

	def insert_series(self, series):
		"""insert series if missing"""
		if frappe.db.get_value("Series", series, "name", order_by="name") == None:
			frappe.db.sql("insert into tabSeries (name, current) values (%s, 0)", (series))

	@frappe.whitelist()
	def update_series_start(self):
		if self.prefix:
			prefix = self.parse_naming_series()
			self.insert_series(prefix)
			frappe.db.sql(
				"update `tabSeries` set current = %s where name = %s", (cint(self.current_value), prefix)
			)
			frappe.msgprint(_("Series Updated Successfully"))
		else:
			frappe.msgprint(_("Please select prefix first"))

	def parse_naming_series(self):
		parts = self.prefix.split(".")

		# Remove ### from the end of series
		if parts[-1] == "#" * len(parts[-1]):
			del parts[-1]

		prefix = parse_naming_series(parts)
		return prefix

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
