# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import re

import frappe
from frappe import _
from frappe.model.document import Document


class Language(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		based_on: DF.Link | None
		enabled: DF.Check
		flag: DF.Data | None
		language_code: DF.Data
		language_name: DF.Data
	# end: auto-generated types

	def validate(self):
		validate_with_regex(self.language_code, "Language Code")

	def before_rename(self, old, new, merge=False):
		validate_with_regex(new, "Name")

	def on_update(self):
		frappe.cache.delete_value("languages_with_name")
		frappe.cache.delete_value("languages")


def validate_with_regex(name, label):
	pattern = re.compile("^[a-zA-Z]+[-_]*[a-zA-Z]+$")
	if not pattern.match(name):
		frappe.throw(
			_(
				"""{0} must begin and end with a letter and can only contain letters,
				hyphen or underscore."""
			).format(label)
		)


def sync_languages():
	"""Create Language records from frappe/geo/languages.csv"""
	from csv import DictReader

	with open(frappe.get_app_path("frappe", "geo", "languages.csv")) as f:
		reader = DictReader(f)
		for row in reader:
			if not frappe.db.exists("Language", row["language_code"]):
				doc = frappe.new_doc("Language")
				doc.update(row)
				doc.insert()
