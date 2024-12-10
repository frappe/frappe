# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

<<<<<<< HEAD
import json
=======
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
import re

import frappe
from frappe import _
<<<<<<< HEAD
=======
from frappe.defaults import clear_default, set_default
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
from frappe.model.document import Document


class Language(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		based_on: DF.Link | None
<<<<<<< HEAD
		enabled: DF.Check
		flag: DF.Data | None
		language_code: DF.Data
		language_name: DF.Data

	# end: auto-generated types
=======
		date_format: DF.Literal[
			"", "yyyy-mm-dd", "dd-mm-yyyy", "dd/mm/yyyy", "dd.mm.yyyy", "mm/dd/yyyy", "mm-dd-yyyy"
		]
		enabled: DF.Check
		first_day_of_the_week: DF.Literal[
			"", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"
		]
		flag: DF.Data | None
		language_code: DF.Data
		language_name: DF.Data
		number_format: DF.Literal[
			"",
			"#,###.##",
			"#.###,##",
			"# ###.##",
			"# ###,##",
			"#'###.##",
			"#, ###.##",
			"#,##,###.##",
			"#,###.###",
			"#.###",
			"#,###",
		]
		time_format: DF.Literal["", "HH:mm:ss", "HH:mm"]
	# end: auto-generated types

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	def validate(self):
		validate_with_regex(self.language_code, "Language Code")

	def before_rename(self, old, new, merge=False):
		validate_with_regex(new, "Name")

	def on_update(self):
		frappe.cache.delete_value("languages_with_name")
		frappe.cache.delete_value("languages")
<<<<<<< HEAD
=======
		self.update_user_defaults()

	def update_user_defaults(self):
		"""Update user defaults for date, time, number format and first day of the week.

		When we change any settings of a language, the defaults for all users with that language
		should be updated.
		"""
		users = frappe.get_all("User", filters={"language": self.name}, pluck="name")
		for key in ("date_format", "time_format", "number_format", "first_day_of_the_week"):
			if self.has_value_changed(key):
				for user in users:
					if new_value := self.get(key):
						set_default(key, new_value, user)
					else:
						clear_default(key, parent=user)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)


def validate_with_regex(name, label):
	pattern = re.compile("^[a-zA-Z]+[-_]*[a-zA-Z]+$")
	if not pattern.match(name):
		frappe.throw(
			_(
<<<<<<< HEAD
				"""{0} must begin and end with a letter and can only contain letters,
				hyphen or underscore."""
=======
				"""{0} must begin and end with a letter and can only contain letters, hyphen or underscore."""
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			).format(label)
		)


<<<<<<< HEAD
def export_languages_json():
	"""Export list of all languages"""
	languages = frappe.get_all("Language", fields=["name", "language_name"])
	languages = [{"name": d.language_name, "code": d.name} for d in languages]

	languages.sort(key=lambda a: a["code"])

	with open(frappe.get_app_path("frappe", "geo", "languages.json"), "w") as f:
		f.write(frappe.as_json(languages))


def sync_languages():
	"""Sync frappe/geo/languages.json with Language"""
	with open(frappe.get_app_path("frappe", "geo", "languages.json")) as f:
		data = json.loads(f.read())

	for l in data:
		if not frappe.db.exists("Language", l["code"]):
			frappe.get_doc(
				{
					"doctype": "Language",
					"language_code": l["code"],
					"language_name": l["name"],
					"enabled": 1,
				}
			).insert()


def update_language_names():
	"""Update frappe/geo/languages.json names (for use via patch)"""
	with open(frappe.get_app_path("frappe", "geo", "languages.json")) as f:
		data = json.loads(f.read())

	for l in data:
		frappe.db.set_value("Language", l["code"], "language_name", l["name"])
=======
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
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
