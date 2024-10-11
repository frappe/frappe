import datetime
import json
import logging
import os
from collections import defaultdict
from collections.abc import Generator
from functools import cache
from importlib import reload
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import TYPE_CHECKING, Any

import tomli

import frappe
from frappe.model.naming import revert_series_if_last
from frappe.modules import get_doctype_module, get_module_path, load_doctype_module

if TYPE_CHECKING:
	from frappe.model.document import Document

logger = logging.getLogger(__name__)
testing_logger = logging.getLogger("frappe.testing.generators")

datetime_like_types = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)

__all__ = [
	"get_modules",
	"get_missing_records_doctypes",
	"get_missing_records_module_overrides",
	"make_test_records",
	"make_test_records_for_doctype",
	"make_test_objects",
	"load_test_records_for",
]


@cache
def get_modules(doctype) -> (str, ModuleType):
	"""Get the modules for the specified doctype"""
	module = frappe.db.get_value("DocType", doctype, "module")
	try:
		test_module = load_doctype_module(doctype, module, "test_")
		if test_module:
			reload(test_module)
	except ImportError:
		test_module = None

	return module, test_module


# @cache - don't cache the recursion, code depends on its recurn value declining
def get_missing_records_doctypes(doctype) -> list[str]:
	"""Get the dependencies for the specified doctype in a depth-first manner"""
	# If already visited in a prior run
	if doctype in frappe.local.test_objects:
		return []
	else:
		# Infinite recrusion guard (depth-first discovery)
		frappe.local.test_objects[doctype] = []

	module, test_module = get_modules(doctype)
	meta = frappe.get_meta(doctype)
	link_fields = meta.get_link_fields()

	for df in meta.get_table_fields():
		link_fields.extend(frappe.get_meta(df.options).get_link_fields())

	unique_doctypes = dict.fromkeys(df.options for df in link_fields if df.options != "[Select]")

	to_add, to_remove = get_missing_records_module_overrides(test_module)
	unique_doctypes.update(dict.fromkeys(to_add))
	if to_remove:
		unique_doctypes = {k: v for k, v in unique_doctypes.items() if k not in to_remove}

	# Recursive depth-first traversal
	result = []
	for dep_doctype in unique_doctypes:
		result.extend(get_missing_records_doctypes(dep_doctype))

	result.append(doctype)
	return result


def get_missing_records_module_overrides(module) -> [list, list]:
	to_add = []
	to_remove = []
	if hasattr(module, "test_dependencies"):
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"2024-10-09",
			"v17",
			"""test_dependencies was clarified to EXTRA_TEST_RECORD_DEPENDENCIES; migration script: https://github.com/frappe/frappe/pull/28060""",
		)
		to_add += module.test_dependencies

	if hasattr(module, "EXTRA_TEST_RECORD_DEPENDENCIES"):
		to_add += module.EXTRA_TEST_RECORD_DEPENDENCIES

	if hasattr(module, "test_ignore"):
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"2024-10-09",
			"v17",
			"""test_ignore was clarified to IGNORE_TEST_RECORD_DEPENDENCIES; migration script: https://github.com/frappe/frappe/pull/28060""",
		)
		to_remove += module.test_ignore

	if hasattr(module, "IGNORE_TEST_RECORD_DEPENDENCIES"):
		to_remove += module.IGNORE_TEST_RECORD_DEPENDENCIES

	return to_add, to_remove


def load_test_records_for(doctype) -> dict[str, Any] | list:
	module_path = get_module_path(get_doctype_module(doctype), "doctype", frappe.scrub(doctype))

	json_path = os.path.join(module_path, "test_records.json")
	if os.path.exists(json_path):
		if not frappe.flags.deprecation_dumpster_invoked:
			from frappe.deprecation_dumpster import deprecation_warning

			deprecation_warning(
				"2024-10-09",
				"v18",
				"Use TOML files for test records; migration script: https://github.com/frappe/frappe/pull/28065",
			)
		with open(json_path) as f:
			return json.load(f)

	toml_path = os.path.join(module_path, "test_records.toml")
	if os.path.exists(toml_path):
		with open(toml_path, "rb") as f:
			return tomli.load(f)

	else:
		return {}


# Test record generation


def _generate_all_records_towards(doctype, force=False, commit=False):
	"""Generate test records for the given doctype and its dependencies."""
	for _doctype in get_missing_records_doctypes(doctype):
		# Create all test records and yield
		res = list(_generate_records_for(_doctype, force, commit, initial_doctype=doctype))
		yield (_doctype, len(res))


def _generate_records_for(
	doctype: str, force: bool = False, commit: bool = False, initial_doctype: str | None = None
) -> Generator["Document", None, None]:
	"""Create and yield test records for a specific doctype."""
	module: str
	test_module: ModuleType

	logstr = f" {doctype} via {initial_doctype}"

	module, test_module = get_modules(doctype)

	# First prioriry: module's _make_test_records as an escape hatch
	# to completely bypass the standard loading and create test records
	# according to custom logic.
	if hasattr(test_module, "_make_test_records"):
		logger.warning("    ↺" + logstr)
		testing_logger.info(
			f" Made  + {doctype:<30} via {initial_doctype} through {test_module._make_test_records}"
		)
		yield from test_module._make_test_records()

	else:
		test_records: list

		# Second Priority: module's test_records attribute
		if hasattr(test_module, "test_records"):
			test_records = test_module.test_records

		# Third priority: module's test_records.toml
		else:
			test_records = load_test_records_for(doctype)

		if not test_records:
			logger.warning("    ➛ " + logstr + " (missing)")
			print_mandatory_fields(doctype, initial_doctype)
			return

		if isinstance(test_records, list):
			test_records = _transform_legacy_json_records(test_records, doctype)

		logger.warning("    ↺ " + logstr)
		testing_logger.info(f" Synced  + {doctype:<30} via {initial_doctype}")

		yield from _sync_records(doctype, test_records, force, commit=commit)


def _sync_records(
	doctype: str, test_records: dict[str, list], reset: bool = False, commit: bool = False
) -> Generator["Document", None, None]:
	"""Generate test objects from provided records, with caching and persistence."""
	# NOTE: We use file-based, per-site persistence visited log in order to not
	# create same records twice for on multiple test runs
	test_record_log_instance = TestRecordLog()
	if not reset and doctype in test_record_log_instance.get():
		yield from test_record_log_instance.get_records(doctype)

	for _doctype, records in test_records.items():
		created = []
		for record in records:
			# Fix the input; better late than never
			if "doctype" not in record:
				record["doctype"] = _doctype
			_rec = _try_create(record)
			# convert_dates_to_str: same as when loaded from log file above
			_rec = _rec.as_dict(convert_dates_to_str=True)
			created.append(_rec)
			frappe.local.test_objects[_doctype].append(MappingProxyType(_rec))

		_logstr = f"{_doctype} ({len(created)})"

		test_record_log_instance.add(_doctype, created)
		testing_logger.info(f"         > {_logstr:<30} via {doctype} to DB and journal")
		yield from created


def _try_create(record, reset=False, commit=False) -> "Document":
	"""Create a single test document from the given record data."""

	def revert_naming(d):
		if getattr(d, "naming_series", None):
			revert_series_if_last(d.naming_series, d.name)

	if not reset:
		frappe.db.savepoint("creating_test_record")

	d = frappe.copy_doc(record)

	if d.meta.get_field("naming_series"):
		if not d.naming_series:
			d.naming_series = "_T-" + d.doctype + "-"

	if record.get("name"):
		d.name = record.get("name")
	else:
		d.set_new_name()

	if frappe.db.exists(d.doctype, d.name) and not reset:
		frappe.db.rollback(save_point="creating_test_record")
		# do not create test records, if already exists
		return frappe.get_doc(d.doctype, d.name)

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
		if d.flags.ignore_these_exceptions_in_test and e.__class__ in d.flags.ignore_these_exceptions_in_test:
			revert_naming(d)
		else:
			logger.debug(f"Error in making test record for {d.doctype} {d.name}")
			raise

	if commit:
		frappe.db.commit()

	return d


def print_mandatory_fields(doctype, initial_doctype):
	"""Print mandatory fields for the specified doctype"""
	meta = frappe.get_meta(doctype)
	msg = []
	head = f"Missing - {doctype:<30}"
	if initial_doctype:
		head += f" via {initial_doctype}"
	msg.append(head)
	msg.append(f"Autoname {meta.autoname or '':<30}")
	mandatory_fields = meta.get("fields", {"reqd": 1})
	if mandatory_fields:
		msg.append("Mandatory Fields")
		for d in mandatory_fields:
			field = f"{d.parent} {d.fieldname} ({d.fieldtype})"
			if d.options:
				opts = d.options.splitlines()
				field += f" opts: {','.join(opts)}"
			msg.append(field)
	testing_logger.debug(" | ".join(msg))


PERSISTENT_TEST_LOG_FILE = ".test_records.jsonl"


class TestRecordLog:
	def __init__(self):
		self.log_file = Path(frappe.get_site_path(PERSISTENT_TEST_LOG_FILE))
		self._log = None

	def get(self):
		if self._log is None:
			self._log = self._read_log()
		return self._log

	def get_records(self, doctype):
		log = self.get()
		return log.get(doctype, [])

	def add(self, doctype, records: list):
		if records:
			self._append_to_log(doctype, records)
			if self._log is None:
				self.get()
			self._log.setdefault(doctype, []).extend(records)
			testing_logger.debug(f"        > {doctype:<30} to {self.log_file}")

	def _append_to_log(self, doctype, records):
		entry = {"doctype": doctype, "records": records}
		with self.log_file.open("a") as f:
			f.write(frappe.as_json(entry, indent=None) + "\n")

	def _read_log(self):
		log = {}
		if self.log_file.exists():
			with self.log_file.open() as f:
				for line in f:
					entry = json.loads(line)
					doctype = entry["doctype"]
					records = entry["records"]
					log.setdefault(doctype, []).extend(records)
		return log


def _after_install_clear_test_log():
	log_file_path = frappe.get_site_path(PERSISTENT_TEST_LOG_FILE)
	if os.path.exists(log_file_path):
		os.remove(log_file_path)


def make_test_records(doctype, force=False, commit=False):
	"""Generate test records for the given doctype and its dependencies."""
	return list(_generate_all_records_towards(doctype, force, commit))


def make_test_records_for_doctype(doctype, force=False, commit=False):
	"""Create test records for a specific doctype."""
	return list(r["name"] for r in _generate_records_for(doctype, force, commit))


def make_test_objects(doctype=None, test_records=None, reset=False, commit=False):
	"""Generate test objects from provided records, with caching and persistence."""
	if test_records is None:
		test_records = load_test_records_for(doctype)

	# Deprecated JSON import - make it comply
	if isinstance(test_records, list):
		test_records = _transform_legacy_json_records(test_records, doctype)
	return list(r["name"] for r in _sync_records(doctype, test_records, reset, commit))


def _transform_legacy_json_records(test_records, doctype):
	_test_records = defaultdict(list)
	for _record in test_records:
		_dt = _record.get("doctype", doctype)
		_record["doctype"] = _dt
		_test_records[_dt].append(_record)
	return _test_records
