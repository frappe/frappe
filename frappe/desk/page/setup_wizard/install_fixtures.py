# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe import _

default_genders = ["Male", "Female", "Other"]

default_salutations = ["Dr.", "Mr.", "Ms.", "Mx.", "Sir", "Dame", "Esq.", "Lady", "Lord", "Mrs.", "Sire", "Madam", "Miss.", "Master", "Proff.", "Captain", "Mistress", "Gentleman", "President", "Principal"]

def install():
	records = [{'doctype': 'Gender', 'gender': _(d)} for d in default_genders]
	records += [{'doctype': 'Salutation', 'salutation': _(d)} for d in default_salutations]

	for r in records:
		doc = frappe.new_doc(r.get("doctype"))
		doc.update(r)

		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError, e:
			# pass DuplicateEntryError and continue
			if e.args and e.args[0]==doc.doctype and e.args[1]==doc.name:
				# make sure DuplicateEntryError is for the exact same doc and not a related doc
				pass
			else:
				raise