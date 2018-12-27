# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import hashlib
from frappe import _
from frappe.utils import format_datetime

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)

	return columns, data

def get_data(filters=None):

	logs = frappe.db.sql("SELECT * FROM `tabTransaction Log` order by creation desc ", as_dict=1)
	result = []
	for l in logs:
		row_index = int(l.row_index)
		if row_index > 1:
			previous_hash = frappe.db.sql("SELECT chaining_hash FROM `tabTransaction Log` WHERE row_index = {0}".format(row_index - 1))
			if not previous_hash:
				integrity = False
			else:
				integrity = check_data_integrity(l.chaining_hash, l.transaction_hash, l.previous_hash, previous_hash[0][0])

			result.append([_(str(integrity)), _(l.reference_doctype), l.document_name, l.owner, l.modified_by, format_datetime(l.timestamp, "YYYYMMDDHHmmss")])
		else:
			result.append([_("First Transaction"), _(l.reference_doctype), l.document_name, l.owner, l.modified_by, format_datetime(l.timestamp, "YYYYMMDDHHmmss")])

	return result

def check_data_integrity(chaining_hash, transaction_hash, registered_previous_hash, previous_hash):
	if registered_previous_hash != previous_hash:
		return False

	calculated_chaining_hash = calculate_chain(transaction_hash, previous_hash)

	if calculated_chaining_hash != chaining_hash:
		return False
	else:
		return True

def calculate_chain(transaction_hash, previous_hash):
	sha = hashlib.sha256()
	sha.update(str(transaction_hash) + str(previous_hash))
	return sha.hexdigest()


def get_columns(filters=None):
	columns = [
		{
			"label": _("Chain Integrity"),
			"fieldname": "chain_integrity",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Reference Doctype"),
			"fieldname": "reference_doctype",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Reference Name"),
			"fieldname": "reference_name",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Owner"),
			"fieldname": "owner",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Modified By"),
			"fieldname": "modified_by",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Timestamp"),
			"fieldname": "timestamp",
			"fieldtype": "Data",
			"width": 100
		}
	]
	return columns
