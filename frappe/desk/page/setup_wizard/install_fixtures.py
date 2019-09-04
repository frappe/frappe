# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe import _

def install():
	update_genders_and_salutations()
	update_global_search_doctypes()

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

def update_global_search_doctypes():
	global_searches_doctypes = ["Contact", "Address"]
	global_search_documents = []

	global_search_settings = frappe.get_single("Global Search Settings")
	global_search_settings.enabled = 1

	for d in global_searches_doctypes:
		global_search_documents.append({"document": d})

	global_search_settings.save(ignore_permissions=True)