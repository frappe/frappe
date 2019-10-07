# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document

class DocumentTypeMapping(Document):
	def get_mapped_doc(self, update):
		doc = frappe._dict(json.loads(update))
		for mapping in self.field_mapping:
			if doc.get(mapping.remote_fieldname):
				#copy value into local fieldname key and remove remote fieldname key
				doc[mapping.local_fieldname] = doc[mapping.remote_fieldname]
				doc.pop(mapping.remote_fieldname, None)
		doc['doctype'] = self.local_doctype
		return frappe.as_json(doc)