import json
import frappe

from frappe.utils import cstr

queue_prefix = 'insert_queue_for_'

@frappe.whitelist()
def deferred_insert(doctype, records):
	frappe.cache().rpush(queue_prefix + doctype, records)

def save_to_db():
	queue_keys = frappe.cache().get_keys(queue_prefix)
	for key in queue_keys:
		record_count = 0
		queue_key = get_key_name(key)
		doctype = get_doctype_name(key)
		while frappe.cache().llen(queue_key) > 0 and record_count <= 500:
			records = frappe.cache().lpop(queue_key)
			records = json.loads(records.decode('utf-8'))
			if isinstance(records, dict):
				record_count += 1
				insert_record(records, doctype)
				continue
			for record in records:
				record_count += 1
				insert_record(record, doctype)

	frappe.db.commit()

def insert_record(record, doctype):
	if not record.get('doctype'):
		record['doctype'] = doctype
	try:
		doc = frappe.get_doc(record)
		doc.insert()
	except Exception as e:
		print(e, doctype)

def get_key_name(key):
	return cstr(key).split('|')[1]

def get_doctype_name(key):
	return cstr(key).split(queue_prefix)[1]
