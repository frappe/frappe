# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import hashlib
import json
import os

import frappe
from frappe.model.base_document import get_controller
from frappe.modules import get_module_path, scrub_dt_dn
from frappe.query_builder import DocType
from frappe.utils import get_datetime, now


def calculate_hash(path: str) -> str:
	"""Calculate and return md5 hash of the file in binary mode.

	Args:
	        path (str): Path to the file to be hashed
	"""
	hash_md5 = hashlib.md5(usedforsecurity=False)
	with open(path, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()


ignore_values = {
	"Report": ["disabled", "prepared_report", "add_total_row"],
	"Print Format": ["disabled"],
	"Notification": ["enabled"],
	"Print Style": ["disabled"],
	"Module Onboarding": ["is_complete"],
	"Onboarding Step": ["is_complete", "is_skipped"],
	"Workspace": ["is_hidden"],
}

ignore_doctypes = [""]


def import_files(
	module, dt=None, dn=None, force: bool = False, pre_process=None, reset_permissions: bool = False
):
	if isinstance(module, list):
		return [
			import_file(
				m[0],
				m[1],
				m[2],
				force=force,
				pre_process=pre_process,
				reset_permissions=reset_permissions,
			)
			for m in module
		]
	else:
		return import_file(
			module, dt, dn, force=force, pre_process=pre_process, reset_permissions=reset_permissions
		)


def import_file(module, dt, dn, force: bool = False, pre_process=None, reset_permissions: bool = False):
	"""Sync a file from txt if modifed, return false if not updated"""
	path = get_file_path(module, dt, dn)
	return import_file_by_path(path, force, pre_process=pre_process, reset_permissions=reset_permissions)


def get_file_path(module, dt, dn):
	dt, dn = scrub_dt_dn(dt, dn)

	path = os.path.join(get_module_path(module), os.path.join(dt, dn, f"{dn}.json"))

	return path


def import_file_by_path(
	path: str,
	force: bool = False,
	data_import: bool = False,
	pre_process=None,
	ignore_version: bool | None = None,
	reset_permissions: bool = False,
) -> bool:
	"""Import file from the given path.

	Some conditions decide if a file should be imported or not.
	Evaluation takes place in the order they are mentioned below.

	- Check if `force` is true. Import the file. If not, move ahead.
	- Get `db_modified_timestamp`(value of the modified field in the database for the file).
	        If the return is `none,` this file doesn't exist in the DB, so Import the file. If not, move ahead.
	- Check if there is a hash in DB for that file. If there is, Calculate the Hash of the file to import and compare it with the one in DB if they are not equal.
	        Import the file. If Hash doesn't exist, move ahead.
	- Check if `db_modified_timestamp` is older than the timestamp in the file; if it is, we import the file.

	If timestamp comparison happens for doctypes, that means the Hash for it doesn't exist.
	So, even if the timestamp is newer on DB (When comparing timestamps), we import the file and add the calculated Hash to the DB.
	So in the subsequent imports, we can use hashes to compare. As a precautionary measure, the timestamp is updated to the current time as well.

	Args:
	        path (str): Path to the file.
	        force (bool, optional): Load the file without checking any conditions. Defaults to False.
	        data_import (bool, optional): [description]. Defaults to False.
	        pre_process ([type], optional): Any preprocesing that may need to take place on the doc. Defaults to None.
	        ignore_version (bool, optional): ignore current version. Defaults to None.
	        reset_permissions (bool, optional): reset permissions for the file. Defaults to False.

	Return True if import takes place, False if it wasn't imported.
	"""
	try:
		docs = read_doc_from_file(path)
	except OSError:
		print(f"{path} missing")
		return

	calculated_hash = calculate_hash(path)

	if docs:
		if not isinstance(docs, list):
			docs = [docs]

		for doc in docs:
			# modified timestamp in db, none if doctype's first import
			db_modified_timestamp = frappe.db.get_value(doc["doctype"], doc["name"], "modified")
			is_db_timestamp_latest = db_modified_timestamp and (
				get_datetime(doc.get("modified")) <= get_datetime(db_modified_timestamp)
			)

			if not force and db_modified_timestamp:
				stored_hash = None
				if doc["doctype"] == "DocType":
					try:
						stored_hash = frappe.db.get_value(doc["doctype"], doc["name"], "migration_hash")
					except Exception:
						pass

				# if hash exists and is equal no need to update
				if stored_hash and stored_hash == calculated_hash:
					continue

				# if hash doesn't exist, check if db timestamp is same as json timestamp, add hash if from doctype
				if is_db_timestamp_latest and doc["doctype"] != "DocType":
					continue

			import_doc(
				docdict=doc,
				data_import=data_import,
				pre_process=pre_process,
				ignore_version=ignore_version,
				reset_permissions=reset_permissions,
				path=path,
			)

			if doc["doctype"] == "DocType":
				doctype_table = DocType("DocType")
				frappe.qb.update(doctype_table).set(doctype_table.migration_hash, calculated_hash).where(
					doctype_table.name == doc["name"]
				).run()

			new_modified_timestamp = doc.get("modified")

			# if db timestamp is newer, hash must have changed, must update db timestamp
			if is_db_timestamp_latest and doc["doctype"] == "DocType":
				new_modified_timestamp = now()

			if new_modified_timestamp:
				update_modified(new_modified_timestamp, doc)

	return True


def read_doc_from_file(path):
	doc = None
	if os.path.exists(path):
		with open(path) as f:
			try:
				doc = json.loads(f.read())
			except ValueError:
				print(f"bad json: {path}")
				raise
	else:
		raise OSError("%s missing" % path)

	return doc


def update_modified(original_modified, doc) -> None:
	# since there is a new timestamp on the file, update timestamp in
	if doc["doctype"] == doc["name"] and doc["name"] != "DocType":
		singles_table = DocType("Singles")

		frappe.qb.update(singles_table).set(singles_table.value, original_modified).where(
			singles_table["field"] == "modified",  # singles_table.field is a method of pypika Selectable
		).where(singles_table.doctype == doc["name"]).run()
	else:
		doctype_table = DocType(doc["doctype"])

		frappe.qb.update(doctype_table).set(doctype_table.modified, original_modified).where(
			doctype_table.name == doc["name"]
		).run()


def import_doc(
	docdict,
	data_import: bool = False,
	pre_process=None,
	ignore_version=None,
	reset_permissions: bool = False,
	path=None,
):
	frappe.flags.in_import = True
	docdict["__islocal"] = 1

	controller = get_controller(docdict["doctype"])
	if controller and hasattr(controller, "prepare_for_import") and callable(controller.prepare_for_import):
		controller.prepare_for_import(docdict)

	doc = frappe.get_doc(docdict)

	reset_tree_properties(doc)
	load_code_properties(doc, path)

	doc.run_method("before_import")

	doc.flags.ignore_version = ignore_version
	if pre_process:
		pre_process(doc)

	if frappe.db.exists(doc.doctype, doc.name):
		delete_old_doc(doc, reset_permissions)

	doc.flags.ignore_links = True
	if not data_import:
		doc.flags.ignore_validate = True
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True

	doc.insert()

	frappe.flags.in_import = False

	return doc


def load_code_properties(doc, path) -> None:
	"""Load code files stored in separate files with extensions"""
	if path:
		if hasattr(doc, "get_code_fields"):
			dirname, filename = os.path.split(path)
			for key, extn in doc.get_code_fields().items():
				codefile = os.path.join(dirname, filename.split(".", 1)[0] + "." + extn)
				if os.path.exists(codefile):
					with open(codefile) as txtfile:
						doc.set(key, txtfile.read())


def delete_old_doc(doc, reset_permissions) -> None:
	ignore = []
	old_doc = frappe.get_doc(doc.doctype, doc.name)

	if doc.doctype in ignore_values:
		# update ignore values
		for key in ignore_values.get(doc.doctype) or []:
			doc.set(key, old_doc.get(key))

	# update ignored docs into new doc
	for df in doc.meta.get_table_fields():
		if df.options in ignore_doctypes and not reset_permissions:
			doc.set(df.fieldname, [])
			ignore.append(df.options)

	# delete old
	frappe.delete_doc(doc.doctype, doc.name, force=1, ignore_doctypes=ignore, for_reload=True)

	doc.flags.ignore_children_type = ignore


def reset_tree_properties(doc) -> None:
	# Note on Tree DocTypes:
	# The tree structure is maintained in the database via the fields "lft" and
	# "rgt". They are automatically set and kept up-to-date. Importing them
	# would destroy any existing tree structure.
	if getattr(doc.meta, "is_tree", None) and any([doc.lft, doc.rgt]):
		print(f'Ignoring values of `lft` and `rgt` for {doc.doctype} "{doc.name}"')
		doc.lft = None
		doc.rgt = None
