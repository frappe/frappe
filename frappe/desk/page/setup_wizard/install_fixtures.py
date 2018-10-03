# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe import _
import json
import copy

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

def bulid_administrative_area_tree(administrative_areas, country):
	administrative_states = [area for area in administrative_areas if area['administrative_area_type'] == "state"]
	lft = 1
	for state in administrative_states:
		all_children = [area for area in administrative_areas if area['parent_unique_name'].startswith(state['self_unique_name'])]
		all_county_children = [area for area in administrative_areas if area['parent_unique_name'] == state['self_unique_name']]
		rgt = lft + 2*len(all_children) + 1
		state.update({"lft": lft, "rgt": rgt})
		if (rgt - lft) == 1:
			lft = lft + 2
		else:
			lft = lft + 1
			for county in all_county_children:
				all_children = [area for area in administrative_areas if area['parent_unique_name'].startswith(county['self_unique_name'])]
				all_city_children = [area for area in administrative_areas if area['parent_unique_name'] == county['self_unique_name']]
				rgt = lft + 2*len(all_children) + 1
				county.update({"lft": lft, "rgt": rgt})
				if (rgt - lft) == 1:
					lft = lft + 2
				else:
					lft = lft + 1
					for city in all_city_children:
						all_children = [area for area in administrative_areas if city['self_unique_name'] in area['parent_unique_name']]
						all_pincode_children = [area for area in administrative_areas if area['parent_unique_name'] == city['self_unique_name']]
						rgt = lft + 2*len(all_children) + 1
						city.update({"lft": lft, "rgt": rgt})
						if (rgt - lft) == 1:
							lft = lft + 2
						else:
							lft = lft + 1
							for pincode in all_pincode_children:
								pincode.update({"lft": lft, "rgt": lft + 1})
								lft = lft + 2
							lft = lft + 1
					lft = lft + 1
			lft = lft + 1


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
			"lft": 0,
			"rgt": 2*len(administrative_areas) + 1
		}
		make_fixture_record(country_record)
		for record in administrative_areas:
			record.update({
				"parent_unique_name": "".join(record['parent']),
				"self_unique_name": "".join(record['parent']) + "" + record['title']
			})

		# Calculate lft, rgt and later use db_insert() to speed up
		bulid_administrative_area_tree(administrative_areas, country)

		# add other administrative areas for the country selected in setup if data available in aa.jaon file

		administrative_areas_copy = copy.deepcopy(administrative_areas)  # copy by value
		for record in administrative_areas:
			record.update({
				"doctype": "Administrative Area",
				"parent_administrative_area": get_parent_name(country, record, administrative_areas, administrative_areas_copy),
				"is_group": 1
			})
			del record['parent']
			del record['parent_unique_name']
			del record['self_unique_name']
			make_fixture_record(record)


def get_parent_name(country, record, administrative_areas, administrative_areas_copy):
	if record['parent_unique_name'] == "":
		return country.title()
	else:
		parent_details = [area for area in administrative_areas_copy if area['self_unique_name'] == record['parent_unique_name']]
		if len(parent_details) == 0:
			frappe.throw("wrong parent hierarchy")
		elif len(parent_details) > 1:
			frappe.throw("duplicate entry")
		else:
			parent_name = [admin_area for admin_area in administrative_areas if parent_details[0]['lft'] == admin_area['lft'] and parent_details[0]['rgt'] == admin_area['rgt'] and parent_details[0]['title'] == admin_area['title']]
			return parent_name[0]['name']


def make_fixture_record(record):
	from frappe.modules import scrub
	doc = frappe.new_doc(record.get("doctype"))
	doc.update(record)
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
