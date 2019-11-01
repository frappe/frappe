# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document
from frappe.utils.background_jobs import get_jobs
from frappe.model import no_value_fields, table_fields

class UpdateLog(Document):
	def after_insert(self):
		'''Send update notification updates to event consumers whenever update log is generated'''
		enqueued_method = 'frappe.events_streaming.doctype.event_consumer.event_consumer.notify_event_consumers'
		jobs = get_jobs()
		if not jobs or enqueued_method not in jobs[frappe.local.site]:
			frappe.enqueue(enqueued_method, queue='long', enqueue_after_commit=True)

def get_update(old, new, for_child=False):
	'''Get document objects with updates only

	If there is a change, then returns a dict like:

		{
			"changed"    : {fieldname1: new_value1, fieldname2: new_value2, }, 
			"added"      : {table_fieldname1: [{row_dict1}, {row_dict2}], },
			"removed"    : {table_fieldname1: [row_name1, row_name2], },
			"row_changed": {table_fieldname1: 
				{
					child_fieldname1: new_val,
					child_fieldname2: new_val
				},
			},

		}'''
	if not new:
		return None

	out = frappe._dict(changed = {}, added = {}, removed = {}, row_changed = {})
	for df in new.meta.fields:
		if df.fieldtype in no_value_fields and df.fieldtype not in table_fields:
			continue

		old_value, new_value = old.get(df.fieldname), new.get(df.fieldname)

		if df.fieldtype in table_fields:
			# make maps
			old_row_by_name, new_row_by_name = {}, {}
			for d in old_value:
				old_row_by_name[d.name] = d
			for d in new_value:
				new_row_by_name[d.name] = d

			# check rows for additions, changes
			for i, d in enumerate(new_value):
				if d.name in old_row_by_name:
					diff = get_update(old_row_by_name[d.name], d, for_child=True)
					if diff and diff.changed:
						if not out.row_changed.get(df.fieldname):
							out.row_changed[df.fieldname] = []
						diff.changed['name'] = d.name
						out.row_changed[df.fieldname].append(diff.changed)
				else:
					if not out.added.get(df.fieldname):
						out.added[df.fieldname] = []
					out.added[df.fieldname].append(d.as_dict())

			# check for deletions
			for d in old_value:
				if not d.name in new_row_by_name:
					if not out.removed.get(df.fieldname):
						out.removed[df.fieldname] = []
					out.removed[df.fieldname].append(d.name)

		elif (old_value != new_value):
			out.changed[df.fieldname] = new_value

	# docstatus
	if not for_child and old.docstatus != new.docstatus:
		out.changed.append(['docstatus', old.docstatus, new.docstatus])

	if any((out.changed, out.added, out.removed, out.row_changed)):
		return out

	else:
		return None