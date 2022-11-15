# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import cProfile
import importlib
import json
import os
import pstats
import sys
import time
import unittest
from importlib import reload
from io import StringIO

import frappe
import frappe.utils.scheduler
from frappe.model.naming import revert_series_if_last
from frappe.modules import get_module_name, load_doctype_module
from frappe.utils import cint

unittest_runner = unittest.TextTestRunner
SLOW_TEST_THRESHOLD = 2


def xmlrunner_wrapper(output):
	"""Convenience wrapper to keep method signature unchanged for XMLTestRunner and TextTestRunner"""
	try:
		import xmlrunner
	except ImportError:
		print("Development dependencies are required to execute this command. To install run:")
		print("$ bench setup requirements --dev")
		raise

	def _runner(*args, **kwargs):
		kwargs["output"] = output
		return xmlrunner.XMLTestRunner(*args, **kwargs)

	return _runner


def main(
	app=None,
	module=None,
	doctype=None,
	module_def=None,
	verbose=False,
	tests=(),
	force=False,
	profile=False,
	junit_xml_output=None,
	ui_tests=False,
	doctype_list_path=None,
	skip_test_records=False,
	failfast=False,
	case=None,
):
	global unittest_runner

	if doctype_list_path:
		app, doctype_list_path = doctype_list_path.split(os.path.sep, 1)
		with open(frappe.get_app_path(app, doctype_list_path)) as f:
			doctype = f.read().strip().splitlines()

	if ui_tests:
		print(
			"Selenium testing has been deprecated\nUse bench --site {site_name} run-ui-tests for Cypress tests"
		)

	xmloutput_fh = None
	if junit_xml_output:
		xmloutput_fh = open(junit_xml_output, "wb")
		unittest_runner = xmlrunner_wrapper(xmloutput_fh)
	else:
		unittest_runner = unittest.TextTestRunner

	try:
		frappe.flags.print_messages = verbose
		frappe.flags.in_test = True

		if not frappe.db:
			frappe.connect()

		# workaround! since there is no separate test db
		frappe.clear_cache()
		scheduler_disabled_by_user = frappe.utils.scheduler.is_scheduler_disabled()
		if not scheduler_disabled_by_user:
			frappe.utils.scheduler.disable_scheduler()

		set_test_email_config()

		if not frappe.flags.skip_before_tests:
			if verbose:
				print('Running "before_tests" hooks')
			for fn in frappe.get_hooks("before_tests", app_name=app):
				frappe.get_attr(fn)()

		if doctype:
			ret = run_tests_for_doctype(
				doctype, verbose, tests, force, profile, failfast=failfast, junit_xml_output=junit_xml_output
			)
		elif module_def:
			doctypes = frappe.db.get_list(
				"DocType", filters={"module": module_def, "istable": 0}, pluck="name"
			)
			ret = run_tests_for_doctype(
				doctypes, verbose, tests, force, profile, failfast=failfast, junit_xml_output=junit_xml_output
			)
		elif module:
			ret = run_tests_for_module(
				module,
				verbose,
				tests,
				profile,
				failfast=failfast,
				junit_xml_output=junit_xml_output,
				case=case,
			)
		else:
			ret = run_all_tests(
				app, verbose, profile, ui_tests, failfast=failfast, junit_xml_output=junit_xml_output
			)

		if not scheduler_disabled_by_user:
			frappe.utils.scheduler.enable_scheduler()

		if frappe.db:
			frappe.db.commit()

		# workaround! since there is no separate test db
		frappe.clear_cache()
		return ret

	finally:
		if xmloutput_fh:
			xmloutput_fh.flush()
			xmloutput_fh.close()


def set_test_email_config():
	frappe.conf.update(
		{
			"auto_email_id": "test@example.com",
			"mail_server": "smtp.example.com",
			"mail_login": "test@example.com",
			"mail_password": "test",
			"admin_password": "admin",
		}
	)


class TimeLoggingTestResult(unittest.TextTestResult):
	def startTest(self, test):
		self._started_at = time.time()
		super().startTest(test)

	def addSuccess(self, test):
		elapsed = time.time() - self._started_at
		name = self.getDescription(test)
		if elapsed >= SLOW_TEST_THRESHOLD:
			self.stream.write(f"\n{name} ({elapsed:.03}s)\n")
		super().addSuccess(test)


def run_all_tests(
	app=None, verbose=False, profile=False, ui_tests=False, failfast=False, junit_xml_output=False
):
	import os

	apps = [app] if app else frappe.get_installed_apps()

	test_suite = unittest.TestSuite()
	for app in apps:
		for path, folders, files in os.walk(frappe.get_pymodule_path(app)):
			for dontwalk in ("locals", ".git", "public", "__pycache__"):
				if dontwalk in folders:
					folders.remove(dontwalk)

			# for predictability
			folders.sort()
			files.sort()

			# print path
			for filename in files:
				if filename.startswith("test_") and filename.endswith(".py") and filename != "test_runner.py":
					# print filename[:-3]
					_add_test(app, path, filename, verbose, test_suite, ui_tests)

	if junit_xml_output:
		runner = unittest_runner(verbosity=1 + cint(verbose), failfast=failfast)
	else:
		runner = unittest_runner(
			resultclass=TimeLoggingTestResult,
			verbosity=1 + cint(verbose),
			failfast=failfast,
			tb_locals=verbose,
		)

	if profile:
		pr = cProfile.Profile()
		pr.enable()

	out = runner.run(test_suite)

	if profile:
		pr.disable()
		s = StringIO()
		ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
		ps.print_stats()
		print(s.getvalue())

	return out


def run_tests_for_doctype(
	doctypes,
	verbose=False,
	tests=(),
	force=False,
	profile=False,
	failfast=False,
	junit_xml_output=False,
):
	modules = []
	if not isinstance(doctypes, (list, tuple)):
		doctypes = [doctypes]

	for doctype in doctypes:
		module = frappe.db.get_value("DocType", doctype, "module")
		if not module:
			print(f"Invalid doctype {doctype}")
			sys.exit(1)

		test_module = get_module_name(doctype, module, "test_")
		if force:
			for name in frappe.db.sql_list("select name from `tab%s`" % doctype):
				frappe.delete_doc(doctype, name, force=True)
		make_test_records(doctype, verbose=verbose, force=force, commit=True)
		modules.append(importlib.import_module(test_module))

	return _run_unittest(
		modules,
		verbose=verbose,
		tests=tests,
		profile=profile,
		failfast=failfast,
		junit_xml_output=junit_xml_output,
	)


def run_tests_for_module(
	module, verbose=False, tests=(), profile=False, failfast=False, junit_xml_output=False, case=None
):
	module = importlib.import_module(module)
	if hasattr(module, "test_dependencies"):
		for doctype in module.test_dependencies:
			make_test_records(doctype, verbose=verbose, commit=True)

	frappe.db.commit()
	return _run_unittest(
		module,
		verbose=verbose,
		tests=tests,
		profile=profile,
		failfast=failfast,
		junit_xml_output=junit_xml_output,
		case=case,
	)


def _run_unittest(
	modules, verbose=False, tests=(), profile=False, failfast=False, junit_xml_output=False, case=None
):
	frappe.db.begin()

	test_suite = unittest.TestSuite()

	if not isinstance(modules, (list, tuple)):
		modules = [modules]

	for module in modules:
		if case:
			module_test_cases = unittest.TestLoader().loadTestsFromTestCase(getattr(module, case))
		else:
			module_test_cases = unittest.TestLoader().loadTestsFromModule(module)
		if tests:
			for each in module_test_cases:
				for test_case in each.__dict__["_tests"]:
					if test_case.__dict__["_testMethodName"] in tests:
						test_suite.addTest(test_case)
		else:
			test_suite.addTest(module_test_cases)

	if junit_xml_output:
		runner = unittest_runner(verbosity=1 + cint(verbose), failfast=failfast)
	else:
		runner = unittest_runner(
			resultclass=TimeLoggingTestResult,
			verbosity=1 + cint(verbose),
			failfast=failfast,
			tb_locals=verbose,
		)

	if profile:
		pr = cProfile.Profile()
		pr.enable()

	frappe.flags.tests_verbose = verbose

	out = runner.run(test_suite)

	if profile:
		pr.disable()
		s = StringIO()
		ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
		ps.print_stats()
		print(s.getvalue())

	return out


def _add_test(app, path, filename, verbose, test_suite=None, ui_tests=False):
	import os

	if os.path.sep.join(["doctype", "doctype", "boilerplate"]) in path:
		# in /doctype/doctype/boilerplate/
		return

	app_path = frappe.get_pymodule_path(app)
	relative_path = os.path.relpath(path, app_path)
	if relative_path == ".":
		module_name = app
	else:
		module_name = "{app}.{relative_path}.{module_name}".format(
			app=app, relative_path=relative_path.replace("/", "."), module_name=filename[:-3]
		)

	module = importlib.import_module(module_name)

	if hasattr(module, "test_dependencies"):
		for doctype in module.test_dependencies:
			make_test_records(doctype, verbose=verbose, commit=True)

	is_ui_test = True if hasattr(module, "TestDriver") else False

	if is_ui_test != ui_tests:
		return

	if not test_suite:
		test_suite = unittest.TestSuite()

	if os.path.basename(os.path.dirname(path)) == "doctype":
		txt_file = os.path.join(path, filename[5:].replace(".py", ".json"))
		if os.path.exists(txt_file):
			with open(txt_file) as f:
				doc = json.loads(f.read())
			doctype = doc["name"]
			make_test_records(doctype, verbose, commit=True)

	test_suite.addTest(unittest.TestLoader().loadTestsFromModule(module))


def make_test_records(doctype, verbose=0, force=False, commit=False):
	if not frappe.db:
		frappe.connect()

	if frappe.flags.skip_test_records:
		return

	for options in get_dependencies(doctype):
		if options == "[Select]":
			continue

		if options not in frappe.local.test_objects:
			frappe.local.test_objects[options] = []
			make_test_records(options, verbose, force, commit=commit)
			make_test_records_for_doctype(options, verbose, force, commit=commit)


def get_modules(doctype):
	module = frappe.db.get_value("DocType", doctype, "module")
	try:
		test_module = load_doctype_module(doctype, module, "test_")
		if test_module:
			reload(test_module)
	except ImportError:
		test_module = None

	return module, test_module


def get_dependencies(doctype):
	module, test_module = get_modules(doctype)
	meta = frappe.get_meta(doctype)
	link_fields = meta.get_link_fields()

	for df in meta.get_table_fields():
		link_fields.extend(frappe.get_meta(df.options).get_link_fields())

	options_list = [df.options for df in link_fields] + [doctype]

	if hasattr(test_module, "test_dependencies"):
		options_list += test_module.test_dependencies

	options_list = list(set(options_list))

	if hasattr(test_module, "test_ignore"):
		for doctype_name in test_module.test_ignore:
			if doctype_name in options_list:
				options_list.remove(doctype_name)

	options_list.sort()

	return options_list


def make_test_records_for_doctype(doctype, verbose=0, force=False, commit=False):
	if not force and doctype in get_test_record_log():
		return

	module, test_module = get_modules(doctype)

	if verbose:
		print("Making for " + doctype)

	if hasattr(test_module, "_make_test_records"):
		frappe.local.test_objects[doctype] += test_module._make_test_records(verbose)

	elif hasattr(test_module, "test_records"):
		if doctype in frappe.local.test_objects:
			frappe.local.test_objects[doctype] += make_test_objects(
				doctype, test_module.test_records, verbose, force, commit=commit
			)
		else:
			frappe.local.test_objects[doctype] = make_test_objects(
				doctype, test_module.test_records, verbose, force, commit=commit
			)

	else:
		test_records = frappe.get_test_records(doctype)
		if test_records:
			frappe.local.test_objects[doctype] += make_test_objects(
				doctype, test_records, verbose, force, commit=commit
			)

		elif verbose:
			print_mandatory_fields(doctype)

	add_to_test_record_log(doctype)


def make_test_objects(doctype, test_records=None, verbose=None, reset=False, commit=False):
	"""Make test objects from given list of `test_records` or from `test_records.json`"""
	records = []

	def revert_naming(d):
		if getattr(d, "naming_series", None):
			revert_series_if_last(d.naming_series, d.name)

	if test_records is None:
		test_records = frappe.get_test_records(doctype)

	for doc in test_records:
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
			frappe.db.rollback()
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
				raise

		records.append(d.name)

		if commit:
			frappe.db.commit()
	return records


def print_mandatory_fields(doctype):
	print("Please setup make_test_records for: " + doctype)
	print("-" * 60)
	meta = frappe.get_meta(doctype)
	print("Autoname: " + (meta.autoname or ""))
	print("Mandatory Fields: ")
	for d in meta.get("fields", {"reqd": 1}):
		print(d.parent + ":" + d.fieldname + " | " + d.fieldtype + " | " + (d.options or ""))
	print()


def add_to_test_record_log(doctype):
	"""Add `doctype` to site/.test_log
	`.test_log` is a cache of all doctypes for which test records are created"""
	test_record_log = get_test_record_log()
	if doctype not in test_record_log:
		frappe.flags.test_record_log.append(doctype)
		with open(frappe.get_site_path(".test_log"), "w") as f:
			f.write("\n".join(filter(None, frappe.flags.test_record_log)))


def get_test_record_log():
	"""Return the list of doctypes for which test records have been created"""
	if "test_record_log" not in frappe.flags:
		if os.path.exists(frappe.get_site_path(".test_log")):
			with open(frappe.get_site_path(".test_log")) as f:
				frappe.flags.test_record_log = f.read().splitlines()
		else:
			frappe.flags.test_record_log = []

	return frappe.flags.test_record_log
