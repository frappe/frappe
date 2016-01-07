# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import unittest, json
import importlib
from frappe.modules import load_doctype_module, get_module_name
from frappe.utils import cstr
import frappe.utils.scheduler

def main(app=None, module=None, doctype=None, verbose=False, tests=(), force=False):
	frappe.flags.print_messages = verbose
	frappe.flags.in_test = True

	if not frappe.db:
		frappe.connect()

	# if not frappe.conf.get("db_name").startswith("test_"):
	# 	raise Exception, 'db_name must start with "test_"'

	# workaround! since there is no separate test db
	frappe.clear_cache()
	frappe.utils.scheduler.disable_scheduler()
	set_test_email_config()

	if verbose:
		print 'Running "before_tests" hooks'
	for fn in frappe.get_hooks("before_tests", app_name=app):
		frappe.get_attr(fn)()

	if doctype:
		ret = run_tests_for_doctype(doctype, verbose=verbose, tests=tests, force=force)
	elif module:
		ret = run_tests_for_module(module, verbose=verbose, tests=tests)
	else:
		ret = run_all_tests(app, verbose)

	frappe.db.commit()

	# workaround! since there is no separate test db
	frappe.clear_cache()

	return ret

def set_test_email_config():
	frappe.conf.update({
		"auto_email_id": "test@example.com",
		"mail_server": "smtp.example.com",
		"mail_login": "test@example.com",
		"mail_password": "test",
		"admin_password": "admin"
	})

def run_all_tests(app=None, verbose=False):
	import os

	apps = [app] if app else frappe.get_installed_apps()

	test_suite = unittest.TestSuite()
	for app in apps:
		for path, folders, files in os.walk(frappe.get_pymodule_path(app)):
			for dontwalk in ('locals', '.git', 'public'):
				if dontwalk in folders:
					folders.remove(dontwalk)

			# print path
			for filename in files:
				filename = cstr(filename)
				if filename.startswith("test_") and filename.endswith(".py"):
					# print filename[:-3]
					_add_test(path, filename, verbose, test_suite=test_suite)

	return unittest.TextTestRunner(verbosity=1+(verbose and 1 or 0)).run(test_suite)

def run_tests_for_doctype(doctype, verbose=False, tests=(), force=False):
	module = frappe.db.get_value("DocType", doctype, "module")
	test_module = get_module_name(doctype, module, "test_")
	if force:
		for name in frappe.db.sql_list("select name from `tab%s`" % doctype):
			frappe.delete_doc(doctype, name, force=True)
	make_test_records(doctype, verbose=verbose, force=force)
	module = frappe.get_module(test_module)
	return _run_unittest(module, verbose=verbose, tests=tests)

def run_tests_for_module(module, verbose=False, tests=()):
	module = importlib.import_module(module)
	if hasattr(module, "test_dependencies"):
		for doctype in module.test_dependencies:
			make_test_records(doctype, verbose=verbose)

	return _run_unittest(module=module, verbose=verbose, tests=tests)

def _run_unittest(module, verbose=False, tests=()):
	test_suite = unittest.TestSuite()
	module_test_cases = unittest.TestLoader().loadTestsFromModule(module)
	if tests:
		for each in module_test_cases:
			for test_case in each.__dict__["_tests"]:
				if test_case.__dict__["_testMethodName"] in tests:
					test_suite.addTest(test_case)
	else:
		test_suite.addTest(module_test_cases)

	return unittest.TextTestRunner(verbosity=1+(verbose and 1 or 0)).run(test_suite)

def _add_test(path, filename, verbose, test_suite=None):
	import os, imp

	if os.path.sep.join(["doctype", "doctype", "boilerplate"]) in path:
		# in /doctype/doctype/boilerplate/
		return

	module = imp.load_source(filename[:-3], os.path.join(path, filename))

	if getattr(module, "selenium_tests", False) and not frappe.conf.run_selenium_tests:
		return

	if not test_suite:
		test_suite = unittest.TestSuite()

	if os.path.basename(os.path.dirname(path))=="doctype":
		txt_file = os.path.join(path, filename[5:].replace(".py", ".json"))
		with open(txt_file, 'r') as f:
			doc = json.loads(f.read())
		doctype = doc["name"]
		make_test_records(doctype, verbose)

	test_suite.addTest(unittest.TestLoader().loadTestsFromModule(module))

def make_test_records(doctype, verbose=0, force=False):
	if not frappe.db:
		frappe.connect()

	for options in get_dependencies(doctype):
		if options == "[Select]":
			continue

		if not options in frappe.local.test_objects:
			if options in frappe.local.test_objects:
				print "No test records or circular reference for {0}".format(options)
			frappe.local.test_objects[options] = []
			make_test_records(options, verbose, force)
			make_test_records_for_doctype(options, verbose, force)

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

	return options_list

def make_test_records_for_doctype(doctype, verbose=0, force=False):
	module, test_module = get_modules(doctype)

	if verbose:
		print "Making for " + doctype

	if hasattr(test_module, "_make_test_records"):
		frappe.local.test_objects[doctype] += test_module._make_test_records(verbose)

	elif hasattr(test_module, "test_records"):
		frappe.local.test_objects[doctype] += make_test_objects(doctype, test_module.test_records, verbose)

	else:
		test_records = frappe.get_test_records(doctype)
		if test_records:
			frappe.local.test_objects[doctype] += make_test_objects(doctype, test_records, verbose)

		elif verbose:
			print_mandatory_fields(doctype)


def make_test_objects(doctype, test_records, verbose=None):
	records = []

	# if not frappe.get_meta(doctype).issingle:
	# 	existing = frappe.get_all(doctype, filters={"name":("like", "_T-" + doctype + "-%")})
	# 	if existing:
	# 		return [d.name for d in existing]
	#
	# 	existing = frappe.get_all(doctype, filters={"name":("like", "_Test " + doctype + "%")})
	# 	if existing:
	# 		return [d.name for d in existing]

	for doc in test_records:
		if not doc.get("doctype"):
			doc["doctype"] = doctype

		d = frappe.copy_doc(doc)

		if doc.get('name'):
			d.name = doc.get('name')

		if frappe.local.test_objects.get(d.doctype):
			# do not create test records, if already exists
			return []

		if d.meta.get_field("naming_series"):
			if not d.naming_series:
				d.naming_series = "_T-" + d.doctype + "-"

		# submit if docstatus is set to 1 for test record
		docstatus = d.docstatus

		d.docstatus = 0

		try:
			d.run_method("before_test_insert")
			d.insert()

			if docstatus == 1:
				d.submit()
		except frappe.NameError:
			pass

		except Exception, e:
			if d.flags.ignore_these_exceptions_in_test and e.__class__ in d.flags.ignore_these_exceptions_in_test:
				pass

			else:
				raise

		records.append(d.name)

	frappe.db.commit()

	return records

def print_mandatory_fields(doctype):
	print "Please setup make_test_records for: " + doctype
	print "-" * 60
	meta = frappe.get_meta(doctype)
	print "Autoname: " + (meta.autoname or "")
	print "Mandatory Fields: "
	for d in meta.get("fields", {"reqd":1}):
		print d.parent + ":" + d.fieldname + " | " + d.fieldtype + " | " + (d.options or "")
	print
