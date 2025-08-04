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
	"get_missing_records_doctypes",
	"get_missing_records_module_overrides",
	"get_modules",
	"load_test_records_for",
	"make_test_objects",
	"make_test_records",
	"make_test_records_for_doctype",
]


@cache
def get_modules(doctype) -> tuple[str, ModuleType]:
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
def get_missing_records_doctypes(doctype, visited=None) -> list[str]:
	"""Get the dependencies for the specified doctype in a depth-first manner"""

	if visited is None:
		visited = set()

	# If already visited in this or a prior run
	if doctype in visited:
		return []

	# Mark as visited
	visited.add(doctype)

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
		result.extend(get_missing_records_doctypes(dep_doctype, visited))

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


def load_test_records_for(index_doctype) -> dict[str, Any]:
	module_path = get_module_path(get_doctype_module(index_doctype), "doctype", frappe.scrub(index_doctype))

	json_path = os.path.join(module_path, "test_records.json")
	if os.path.exists(json_path):
		with open(json_path) as f:
			return _transform_legacy_json_records(json.load(f), index_doctype)

	toml_path = os.path.join(module_path, "test_records.toml")
	if os.path.exists(toml_path):
		with open(toml_path, "rb") as f:
			return tomli.load(f)

	else:
		return {}


# Test record generation


def _generate_all_records_towards(
	index_doctype, reset=False, commit=False
) -> Generator[tuple[str, int], None, None]:
	"""Generate test records for the given doctype and its dependencies."""

	# NOTE: visited excludes dependency discovery of any index doctype which
	# which had already been loaded into memory prior
	visited = set(frappe.local.test_objects.keys())
	for _index_doctype in get_missing_records_doctypes(index_doctype, visited):
		# Create all test records and yield
		res = list(
			_generate_records_for(_index_doctype, reset=reset, commit=commit, initial_doctype=index_doctype)
		)
		yield (_index_doctype, len(res))


def _generate_records_for(
	index_doctype: str, reset: bool = False, commit: bool = False, initial_doctype: str | None = None
) -> Generator[tuple[str, "Document"], None, None]:
	"""Create and yield test records for a specific doctype."""
	module: str
	test_module: ModuleType

	logstr = f" {index_doctype} via {initial_doctype}"

	module, test_module = get_modules(index_doctype)

	# First prioriry: module's _make_test_records as an escape hatch
	# to completely bypass the standard loading and create test records
	# according to custom logic.
	if hasattr(test_module, "_make_test_records"):
		logger.info("↺" + logstr)
		testing_logger.info(
			f" Made  + {index_doctype:<30} via {initial_doctype} through {test_module._make_test_records}"
		)
		yield from test_module._make_test_records()

	else:
		test_records: list

		# Second Priority: module's test_records attribute
		if hasattr(test_module, "test_records"):
			test_records = test_module.test_records
			if isinstance(test_records, list):
				test_records = _transform_legacy_json_records(test_records, index_doctype)

		# Third priority: module's test_records.toml
		else:
			test_records = load_test_records_for(index_doctype)

		if not test_records:
			logger.info("➛ " + logstr + " (missing)")
			frappe.local.test_objects[index_doctype] = []  # avoid noisy retries on multiple invocations
			print_mandatory_fields(index_doctype, initial_doctype)
			return

		logger.info("↺ " + logstr)
		testing_logger.info(f" Synced  + {index_doctype:<30} via {initial_doctype}")

		yield from _sync_records(index_doctype, test_records, reset=reset, commit=commit)


global test_record_manager_instance
test_record_manager_instance = None


def _sync_records(
	index_doctype: str, test_records: dict[str, list], reset: bool = False, commit: bool = False
) -> Generator[tuple[str, "Document"], None, None]:
	"""Generate test objects for a register doctype from provided records, with caching and persistence."""
	# NOTE: This method is called in roughly these situations:
	# 1. First sync of a index doctype's records
	# 2. Manual sync, e.g. by a secondary call to make_test_records / make_test_objects
	# 3. Manual sync with reset, e.g. simlar secondary call with force=True
	# 4. Re-execution of a test on the same database

	# To keep track of creation across re-execution, we use a file-based, per-site
	# persistence log indexed by the register doctype. It also serves as proof of
	# records at the time of creation and contains the db values

	global test_record_manager_instance
	if test_record_manager_instance is None:
		test_record_manager_instance = TestRecordManager()

	def _load(do_create=True):
		created, loaded = [], []
		# one test record file / source under a single register doctype may have entires for different doctypes
		for _sub_doctype, records in test_records.items():
			for record in records:
				# Fix the input; better late than never
				if "doctype" not in record:
					record["doctype"] = _sub_doctype

				if do_create:
					doc, was_created = _try_create(record, reset, commit)
					if was_created:
						created.append(doc)
					else:
						loaded.append(doc)

				# Important: we load the raw data records into globalTestRecords
				# which best suites the test engineers intentions and expectations
				frappe.local.test_objects[index_doctype].append(MappingProxyType(record))

		if not do_create:
			loaded.extend(test_record_manager_instance.get_records(index_doctype))
			_logstr = f"{index_doctype} ({len(loaded)})"
			testing_logger.info(f"         > {_logstr:<30} into cls.globalTestRecords, only")
		else:
			# we keep an mpty created = [] on purpose to persist proof of prior processing of the index doctype
			test_record_manager_instance.add(index_doctype, created)
			_logstr = f"{index_doctype} ({len(created)} / {len(loaded) + len(created)})"
			testing_logger.info(f"         > {_logstr:<30} into Database & Journal / cls.globalTestRecords")

		for item in created:
			yield ("created", item)
		for item in loaded:
			yield ("loaded", item)

	# Please keep the decision tree intact, even if some branches may seem redundant
	# this is for clarity, documentation and future modifications or enhancements
	# of this critical loading api
	if index_doctype in test_record_manager_instance.get():
		# Scenario: secondary call or re-execution
		if reset:
			# Scenario: secondary call with force
			frappe.local.test_objects[index_doctype] = []
			test_record_manager_instance.remove(index_doctype)
			testing_logger.info(f"         > {index_doctype:<30} removed from journal")
			yield from _load()

		else:
			# Scenario: secondary call without force or re-execution
			if index_doctype not in frappe.local.test_objects:
				# Scenario: re-execution; not yet loaded into memory
				yield from _load(do_create=False)
			else:
				# Scenario: secondary call on the same index doctype; may add more records
				yield from _load()

	else:
		# Scenario: primary call, first load; baseline
		yield from _load()


def _try_create(record, reset=False, commit=False) -> tuple["Document", bool]:
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
		return frappe.get_doc(d.doctype, d.name), False

	# submit if docstatus is set to 1 for test record
	docstatus = d.docstatus

	d.docstatus = 0

	d.run_method("before_test_insert")
	d.insert(ignore_if_duplicate=True)

	if docstatus == 1:
		d.submit()

	if commit:
		frappe.db.commit()

	return d, True


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


class TestRecordManager:
	def __init__(self):
		testing_logger.debug(f"{self} initialized")
		self.log_file = Path(frappe.get_site_path(PERSISTENT_TEST_LOG_FILE))
		self._log = None

	def get(self):
		if self._log is None:
			self._log = self._read_log()
		return self._log

	def get_records(self, index_doctype) -> list["Document"]:
		log = self.get()
		return log.get(index_doctype, [])

	def add(self, index_doctype, records: list["Document"]):
		if records:
			self._append_to_log(index_doctype, records)
			if self._log is None:
				self.get()
			self._log.setdefault(index_doctype, []).extend(records)
			testing_logger.debug(f"        > {index_doctype:<30} ({len(records)}) added to {self.log_file}")

	def remove(self, index_doctype):
		"""
		Remove all records for the specified doctype from the log.
		"""
		if index_doctype in self.get():
			del self._log[index_doctype]
			self._remove_from_log(index_doctype)
			testing_logger.debug(f"        > {index_doctype:<30} deleted from {self.log_file}")

	def _append_to_log(self, index_doctype, records: list["Document"]):
		entry = {"doctype": index_doctype, "records": records}
		with self.log_file.open("a") as f:
			f.write(frappe.as_json(entry, indent=None) + "\n")

	def _read_log(self):
		log = {}
		if self.log_file.exists():
			with self.log_file.open() as f:
				for line in f:
					entry = json.loads(line)
					index_doctype = entry["doctype"]
					records = entry["records"]
					try:
						for r in records:
							log.setdefault(index_doctype, []).append(frappe.get_doc(r["doctype"], r["name"]))
					except frappe.DoesNotExistError as e:
						raise ValueError(
							f"Global test record '{r['name']}' ({r['doctype']}) had been deleted resulting in inconsistent global state."
						) from e
		return log

	def _remove_from_log(self, index_doctype):
		temp_file = self.log_file.with_suffix(".temp")
		with self.log_file.open("r") as input_file, temp_file.open("w") as output_file:
			for line in input_file:
				entry = json.loads(line)
				if entry["doctype"] != index_doctype:
					output_file.write(line)
		temp_file.replace(self.log_file)


def _clear_test_log():
	log_file_path = frappe.get_site_path(PERSISTENT_TEST_LOG_FILE)
	if os.path.exists(log_file_path):
		os.remove(log_file_path)


def make_test_records(doctype, force=False, commit=False):
	"""Generate test records for the given doctype and its dependencies."""
	return list(_generate_all_records_towards(doctype, reset=force, commit=commit))


def make_test_records_for_doctype(doctype, force=False, commit=False):
	"""Create test records for a specific doctype."""
	return list(r.name for tag, r in _generate_records_for(doctype, reset=force, commit=commit))


def make_test_objects(doctype=None, test_records=None, reset=False, commit=False):
	"""Generate test objects from provided records, with caching and persistence."""
	# Legacy JSON import - make it comply
	if isinstance(test_records, list):
		test_records = _transform_legacy_json_records(test_records, doctype)

	if test_records is None:
		test_records = load_test_records_for(doctype)
	return list(r.name for tag, r in _sync_records(doctype, test_records, reset, commit))


def _transform_legacy_json_records(test_records, doctype):
	_test_records = defaultdict(list)
	for _record in test_records:
		_dt = _record.get("doctype", doctype)
		_record["doctype"] = _dt
		_test_records[_dt].append(_record)
	return _test_records
