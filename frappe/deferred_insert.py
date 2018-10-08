import frappe
import json

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
			records = json.loads(records)
			if isinstance(records, dict):
				insert_record(records, doctype)
				continue
			for record in records:
				record_count += 1
				insert_record(record, doctype)

def insert_record(record, doctype):
	if not record['doctype']:
		record['doctype'] = doctype
	try:
		doc = frappe.get_doc(record)
		doc.insert()
	except Exception as e:
		print(e, doctype)

def get_key_name(key):
	return key.split('|')[1]

def get_doctype_name(key):
	return key.split(queue_prefix)[1]


# def save_to_db(doctype):
# 	values=[]
# 	queue_key = 'deferred_insert_queue_for' + doctype
# 	value_key = ''
# 	while frappe.cache().llen(queue_key) > 0:
# 		records = frappe.cache().lpop(queue_key)
# 		records = json.loads(records)
# 		if not value_key: value_key = list(records[0].keys())
# 		value_template = "('{" + "}', '{".join(value_key) + "}')"
# 		for record in records:
# 			if value_key != list(record.keys()):
# 				print('Keys should match for all records', value_key, list(record.keys()))
# 				continue
# 			values.append(value_template.format(**record))

# 	if not values: return

# 	frappe.db.sql('''
# 		INSERT INTO `tab{doctype}` (`{keys}`)
# 		VALUES {values}
# 	'''.format(doctype=doctype, keys="`, `".join(value_key), values=", ".join(values)), debug=1)

# 	frappe.db.commit()