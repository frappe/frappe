# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe import _
import json
import copy

from frappe.utils.nestedset import rebuild_tree

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

@frappe.whitelist()
def make_administrative_area_fixtures():
	frappe.utils.background_jobs.enqueue(
		make_administrative_areas,
		queue="long",
		timeout=36000,
		enqueue_after_commit=True,
	)

def make_administrative_areas():
	"""
	ASSUMPTIONS: 1. Administrative_areas.json file does not have complete duplicates
				 2. There are only 5 levels i.e.country, state, county, city and pincode (hardcoded names)
				 3. In administrative_areas.json child occures after parent

	"""
	#enter country administrative area as root node with no parent
	country = frappe.db.get_value("System Settings", "System Settings", "Country")
	if country == "India":
		with open("../apps/frappe/frappe/geo/administrative_regions/india.json") as f:
			administrative_areas = json.loads(f.read())
		country_record = {
			"doctype": "Administrative Area",
			"title": country,
			"administrative_area_type": "country",
			"is_group": 1,
			"parent": "",
			"parent_unique_name": "",
			"self_unique_name": country.title()
		}
		make_fixture_record(country_record)

		"""
		for an entry in india.json like 
		{"administrative_area_type": "city","parent": ["Telangana","Medak"],"title": "Zaheerabad"}

		parent_unique_name will be TelanganaMedak
		self_unique_name will be TelanganaMedakZaheerabad
		"""

		for record in administrative_areas:
			record.update({
				"parent_unique_name": "".join(record['parent']),
				"self_unique_name": "".join(record['parent']) + "" + record['title']
			})

		for record in administrative_areas:
			record.update({
				"doctype": "Administrative Area",
				"parent_administrative_area": get_parent_name(country, record, administrative_areas),
				"is_group": 1
			})

			make_fixture_record(record)

		# use rebuild_tree function from nestedset to calculate lft, rgt for all nodes
		rebuild_tree("Administrative Area", "parent_administrative_area")


def get_parent_name(country, record, administrative_areas):
	if record['parent_unique_name'] == "":
		return country.title()
	else:
		parent_details = [area for area in administrative_areas if area['self_unique_name'] == record['parent_unique_name']]
		if len(parent_details) == 0:
			frappe.throw("wrong parent hierarchy")
		elif len(parent_details) > 1:
			frappe.throw("duplicate entry")
		else:
			try:
				return parent_details[0]["name"]
			except KeyError:
				frappe.throw("parent occurs after child in json file")
			

def make_fixture_record(record):
	record_to_insert = copy.deepcopy(record)
	# create a copy and delete keys which are not docfields
	del record_to_insert['parent']
	del record_to_insert['parent_unique_name']
	del record_to_insert['self_unique_name']
	
	from frappe.modules import scrub
	doc = frappe.new_doc(record_to_insert.get("doctype"))
	doc.update(record_to_insert)
	# ignore mandatory for root
	parent_link_field = ("parent_" + scrub(doc.doctype))
	if doc.meta.get_field(parent_link_field) and not doc.get(parent_link_field):
		doc.flags.ignore_mandatory = True

	try:
		doc.db_insert()
		record.update({"name": doc.name})
		frappe.db.commit()
	except frappe.DuplicateEntryError as e:
		# pass DuplicateEntryError and continue
		if e.args and e.args[0] == doc.doctype and e.args[1] == doc.name:
			# make sure DuplicateEntryError is for the exact same doc and not a related doc
			pass
		else:
			raise
	except frappe.ValidationError as e:
		area_name = str(e).split(" already exists")[0]
		record.update({"name": area_name})
