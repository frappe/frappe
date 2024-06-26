import json
from typing import TYPE_CHECKING, Union

import redis

import frappe
from frappe.utils import cstr

if TYPE_CHECKING:
	from frappe.model.document import Document

queue_prefix = "insert_queue_for_"

TYPE_UNION_DICT_DOCUMENT = list[Union[dict, "Document"]]
FAILED_RECORDS = list[Union[dict, "Document"]]


def deferred_insert(doctype: str, records: TYPE_UNION_DICT_DOCUMENT | str):
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
	# TODO: can this be async?
	for key in queue_keys:
		queue_key = get_key_name(key)
		doctype = get_doctype_name(key)
		while cache_size := frappe.cache.llen(queue_key):
			records = frappe.cache.lpop(queue_key, count=cache_size)
			records: TYPE_UNION_DICT_DOCUMENT = json.loads(records.decode("utf-8"))
			if failed_records := insert_records(records, doctype):
				frappe.cache.rpush(queue_key, json.dumps(failed_records))


def insert_records(records: TYPE_UNION_DICT_DOCUMENT, doctype: str) -> FAILED_RECORDS:
	"""Inserts records into the database else collects records in order upon failure."""
	failed_records = []
	pending_records = [records] if isinstance(records, dict) else records
	for record in pending_records:
		try:
			insert_record(record, doctype)
		# TODO: refactor to explicit exceptions from generic exception.
		except Exception as e:
			frappe.logger().error(f"Error while inserting deferred {doctype} record: {e}")
			failed_records += [record]
	return failed_records


def insert_record(record: Union[dict, "Document"], doctype: str):
	record.update({"doctype": doctype})
	frappe.get_doc(record).insert()


def get_key_name(key: str) -> str:
	return cstr(key).split("|")[1]


def get_doctype_name(key: str) -> str:
	return cstr(key).split(queue_prefix)[1]
