import datetime
import logging
from functools import cache
from importlib import reload
from pathlib import Path

import frappe
from frappe.model.naming import revert_series_if_last
from frappe.modules import load_doctype_module

logger = logging.getLogger(__name__)

datetime_like_types = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)

__all__ = [
	"get_modules",
	"get_dependencies",
	"make_test_records",
	"make_test_records_for_doctype",
	"make_test_objects",
]


@cache
def get_modules(doctype):
	"""Get the modules for the specified doctype"""
	module = frappe.db.get_value("DocType", doctype, "module")
	try:
		test_module = load_doctype_module(doctype, module, "test_")
		if test_module:
			reload(test_module)
	except ImportError:
		test_module = None

	return module, test_module


@cache
def get_dependencies(doctype):
	"""Get the dependencies for the specified doctype"""
	module, test_module = get_modules(doctype)
	meta = frappe.get_meta(doctype)
	link_fields = meta.get_link_fields()

	for df in meta.get_table_fields():
		link_fields.extend(frappe.get_meta(df.options).get_link_fields())

	options_list = [df.options for df in link_fields]

	if hasattr(test_module, "test_dependencies"):
		options_list += test_module.test_dependencies

	options_list = list(set(options_list))

	if hasattr(test_module, "test_ignore"):
		for doctype_name in test_module.test_ignore:
			if doctype_name in options_list:
				options_list.remove(doctype_name)

	options_list.sort()

	return options_list


# Test record generation


def make_test_records(doctype, force=False, commit=False):
	return list(_make_test_records(doctype, force, commit))


def make_test_records_for_doctype(doctype, force=False, commit=False):
	return list(_make_test_records_for_doctype(doctype, force, commit))


def make_test_objects(doctype, test_records=None, reset=False, commit=False):
	return list(_make_test_objects(doctype, test_records, reset, commit))


def _make_test_records(doctype, force=False, commit=False):
	"""Make test records for the specified doctype"""

	loadme = False

	if doctype not in frappe.local.test_objects:
		loadme = True
		frappe.local.test_objects[doctype] = []  # infinite recursion guard, here

	# First, create test records for dependencies
	for dependency in get_dependencies(doctype):
		if dependency != "[Select]" and dependency not in frappe.local.test_objects:
			yield from _make_test_records(dependency, force, commit)

	# Then, create test records for the doctype itself
	if loadme:
		# Yield the doctype and record length
		yield (
			doctype,
			len(
				# Create all test records
				list(_make_test_records_for_doctype(doctype, force, commit))
			),
		)


def _make_test_records_for_doctype(doctype, force=False, commit=False):
	"""Make test records for the specified doctype"""

	test_record_log_instance = TestRecordLog()
	if not force and doctype in test_record_log_instance.get():
		return

	module, test_module = get_modules(doctype)
	if hasattr(test_module, "_make_test_records"):
		yield from test_module._make_test_records()
	elif hasattr(test_module, "test_records"):
		yield from _make_test_objects(doctype, test_module.test_records, force, commit=commit)
	else:
		test_records = frappe.get_test_records(doctype)
		if test_records:
			yield from _make_test_objects(doctype, test_records, force, commit=commit)
		else:
			print_mandatory_fields(doctype)

	test_record_log_instance.add(doctype)


def _make_test_objects(doctype, test_records=None, reset=False, commit=False):
	"""Generator function to make test objects"""

	def revert_naming(d):
		if getattr(d, "naming_series", None):
			revert_series_if_last(d.naming_series, d.name)

	if test_records is None:
		test_records = frappe.get_test_records(doctype)

	for doc in test_records:
		if not reset:
			frappe.db.savepoint("creating_test_record")

		if not doc.get("doctype"):
			doc["doctype"] = doctype

		d = frappe.copy_doc(doc)

		if d.meta.get_field("naming_series"):
			if not d.naming_series:
				d.naming_series = "_T-" + d.doctype + "-"

		if doc.get("name"):
			d.name = doc.get("name")
		else:
			d.set_new_name()

		if frappe.db.exists(d.doctype, d.name) and not reset:
			frappe.db.rollback(save_point="creating_test_record")
			# do not create test records, if already exists
			continue

		# submit if docstatus is set to 1 for test record
		docstatus = d.docstatus

		d.docstatus = 0

		try:
			d.run_method("before_test_insert")
			d.insert(ignore_if_duplicate=True)

			if docstatus == 1:
				d.submit()

		except frappe.NameError:
			revert_naming(d)

		except Exception as e:
			if (
				d.flags.ignore_these_exceptions_in_test
				and e.__class__ in d.flags.ignore_these_exceptions_in_test
			):
				revert_naming(d)
			else:
				logger.debug(f"Error in making test record for {d.doctype} {d.name}")
				raise

		if commit:
			frappe.db.commit()

		frappe.local.test_objects[doctype] += d.name
		yield d.name


def print_mandatory_fields(doctype):
	"""Print mandatory fields for the specified doctype"""
	meta = frappe.get_meta(doctype)
	logger.warning(f"Please setup make_test_records for: {doctype}")
	logger.warning("-" * 60)
	logger.warning(f"Autoname: {meta.autoname or ''}")
	logger.warning("Mandatory Fields:")
	for d in meta.get("fields", {"reqd": 1}):
		logger.warning(f" - {d.parent}:{d.fieldname} | {d.fieldtype} | {d.options or ''}")
	logger.warning("")


class TestRecordLog:
	def __init__(self):
		self.log_file = Path(frappe.get_site_path(".test_log"))
		self._log = None

	def get(self):
		if self._log is None:
			self._log = self._read_log()
		return self._log

	def add(self, doctype):
		log = self.get()
		if doctype not in log:
			log.append(doctype)
			self._write_log(log)

	def _read_log(self):
		if self.log_file.exists():
			with self.log_file.open() as f:
				return f.read().splitlines()
		return []

	def _write_log(self, log):
		with self.log_file.open("w") as f:
			f.write("\n".join(l for l in log if l is not None))
