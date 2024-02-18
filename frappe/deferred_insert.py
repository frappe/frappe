import json
from typing import TYPE_CHECKING, Union

import redis

import frappe
from frappe.utils import cstr

if TYPE_CHECKING:
	from frappe.model.document import Document

queue_prefix = "insert_queue_for_"


def deferred_insert(doctype: str, records: list[Union[dict, "Document"]] | str):
	if isinstance(records, dict | list):
		_records = json.dumps(records)
	else:
		_records = records

	try:
		frappe.cache.rpush(f"{queue_prefix}{doctype}", _records)
	except redis.exceptions.ConnectionError:
		for record in records:
			insert_record(record, doctype)


def save_to_db():
    queue_keys = frappe.cache.get_keys(queue_prefix)
    batch_size = 500

    for key in queue_keys:
        queue_key = get_key_name(key)
        doctype = get_doctype_name(key)

        while True:
            records_batch = [frappe.cache.lpop(queue_key) for _ in range(batch_size)]
            records_batch = [json.loads(record.decode("utf-8")) for record in records_batch if record]

            if not records_batch:
                break

            for records in records_batch:
                if isinstance(records, dict):
                    insert_record(records, doctype)
                else:
                    for record in records:
                        insert_record(record, doctype)


def insert_record(record: Union[dict, "Document"], doctype: str):
	try:
		record.update({"doctype": doctype})
		frappe.get_doc(record).insert()
	except Exception as e:
		frappe.logger().error(f"Error while inserting deferred {doctype} record: {e}")


def get_key_name(key: str) -> str:
	return cstr(key).split("|")[1]


def get_doctype_name(key: str) -> str:
	return cstr(key).split(queue_prefix)[1]
