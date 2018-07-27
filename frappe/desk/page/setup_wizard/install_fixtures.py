# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe import _

def install():
	update_genders_and_salutations()
	make_administrative_area_fixtures()

@frappe.whitelist()
def update_genders_and_salutations():
	default_genders = [_("Male"), _("Female"), _("Other")]
	default_salutations = [_("Mr"), _("Ms"), _('Mx'), _("Dr"), _("Mrs"), _("Madam"), _("Miss"), _("Master"), _("Prof")]
	records = [{'doctype': 'Gender', 'gender': d} for d in default_genders]
	records += [{'doctype': 'Salutation', 'salutation': d} for d in default_salutations]
	for record in records:
		doc = frappe.new_doc(record.get("doctype"))
		doc.update(record)

		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError as e:
			# pass DuplicateEntryError and continue
			if e.args and e.args[0]==doc.doctype and e.args[1]==doc.name:
				# make sure DuplicateEntryError is for the exact same doc and not a related doc
				pass
			else:
				raise


def make_administrative_area_fixtures():
	"""
	ToDo:
	- [x] read the JSON file
	- [ ] fetch parent doc name based on the title of parent doc
	- [ ] insert a doc of the fixture
	JSON specififcations:
	title: name of the Administrative Area
	parent: list of parents in decreasing order
	Example:
	{ "title": "Maharashtra", "parent": [] }
	"""

	administrative_areas = get_administrative_areas()
	make_administrative_areas(administrative_areas)

def get_administrative_areas():
	with open("administrative_areas.json") as f:
		return json.loads(f)

def make_administrative_areas(administrative_areas):
	records = []
	country = frappe.db.get_value("System Settings", "System Settings", "Country")
	country_record = frappe.get_doc({
		"doctype": "Administrative Area",
		"administrative_area_type": "Country",
		"title": country
	})
	records.append(country_record)
	for record in administrative_areas[country]:
		parents = list(country)
		parents.extend(record["parent"])
		record.update({
			"doctype": "Administrative Area",
			"parent_administrative_area": get_administrative_area_parent_name(parents)
		})
		del record["parent"]
		records.append(record)

	make_fixture_records(records)


def get_administrative_area_parent_name(parents):
	#frappe.db.
	return parent_administrative_area


def make_fixture_records(records):
	from frappe.modules import scrub
	for r in records:
		doc = frappe.new_doc(r.get("doctype"))
		doc.update(r)

		# ignore mandatory for root
		parent_link_field = ("parent_" + scrub(doc.doctype))
		if doc.meta.get_field(parent_link_field) and not doc.get(parent_link_field):
			doc.flags.ignore_mandatory = True

		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError as e:
			# pass DuplicateEntryError and continue
			if e.args and e.args[0]==doc.doctype and e.args[1]==doc.name:
				# make sure DuplicateEntryError is for the exact same doc and not a related doc
				pass
			else:
				raise
