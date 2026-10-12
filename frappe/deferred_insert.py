import json
from typing import TYPE_CHECKING, Union

import redis

import frappe
from frappe.utils import cstr

if TYPE_CHECKING:
	from frappe.model.document import Document

queue_prefix = "insert_queue_for_"


def deferred_insert(doctype: str, records: list[dict | "Document"] | str):
	if isinstance(records, dict | list):
		_records = json.dumps(records)
	else:
		_records = records

	try:
		frappe.cache.rpush(f"{queue_prefix}{doctype}", _records)
	except redis.exceptions.ConnectionError:
		for record in records:
			insert_record(record, doctype)


def save_to_db(doctype: str | None = None):
	queue_keys = [f"{queue_prefix}{doctype}"] if doctype else frappe.cache.get_keys(queue_prefix)
	for key in queue_keys:
		record_count = 0
		uncommitted_records = []
		queue_key = key if doctype else get_key_name(key)
		queue_doctype = doctype or get_doctype_name(key)
		while frappe.cache.llen(queue_key) > 0 and record_count <= 10000:
			records = frappe.cache.lpop(queue_key)
			records = json.loads(records.decode("utf-8"))
			records = [records] if isinstance(records, dict) else records
			for index, record in enumerate(records):
				record_count += 1
				try:
					inserted = insert_record(record, queue_doctype)
				except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
					frappe.db.rollback()
					records_to_retry = [*uncommitted_records, *records[index:]]
					frappe.cache.lpush(queue_key, json.dumps(records_to_retry))
					raise
				if inserted:
					uncommitted_records.append(record)
				if record_count % 100 == 0:
					frappe.db.commit()
					uncommitted_records.clear()


def insert_record(record: dict | "Document", doctype: str):
	try:
		record.update({"doctype": doctype})
		frappe.get_doc(record).insert()
		return True
	except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
		raise
	except Exception as e:
		frappe.logger().error(f"Error while inserting deferred {doctype} record: {e}")
		return False


def get_key_name(key: str) -> str:
	return cstr(key).split("|")[1]


def get_doctype_name(key: str) -> str:
	return cstr(key).split(queue_prefix)[1]
