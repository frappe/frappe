# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import sys
if __name__=="__main__":
	sys.path.extend([".", "app", "lib"])

import webnotes
import unittest

from webnotes.model.meta import has_field
from webnotes.model.code import load_doctype_module, get_module_name
from webnotes.model.doctype import get_link_fields
from webnotes.utils import cstr


def make_test_records(doctype, verbose=0):
	webnotes.flags.mute_emails = True
	if not webnotes.conn:
		webnotes.connect()
	
	for options in get_dependencies(doctype):
		if options.startswith("link:"):
			options = options[5:]
		if options == "[Select]":
			continue
			
		if options not in webnotes.test_objects:
			webnotes.test_objects[options] = []
			make_test_records(options, verbose)
			make_test_records_for_doctype(options, verbose)

def get_modules(doctype):
	module = webnotes.conn.get_value("DocType", doctype, "module")
	test_module = load_doctype_module(doctype, module, "test_")
	if test_module: reload(test_module)

	return module, test_module

def get_dependencies(doctype):
	module, test_module = get_modules(doctype)
	
	options_list = list(set([df.options for df in get_link_fields(doctype)] + [doctype]))
	
	if hasattr(test_module, "test_dependencies"):
		options_list += test_module.test_dependencies
	
	if hasattr(test_module, "test_ignore"):
		for doctype_name in test_module.test_ignore:
			if doctype_name in options_list:
				options_list.remove(doctype_name)
	return options_list

def make_test_records_for_doctype(doctype, verbose=0):
	module, test_module = get_modules(doctype)
	
	if verbose:
		print "Making for " + doctype

	if hasattr(test_module, "make_test_records"):
		webnotes.test_objects[doctype] += test_module.make_test_records(verbose)

	elif hasattr(test_module, "test_records"):
		webnotes.test_objects[doctype] += make_test_objects(doctype, test_module.test_records, verbose)
	elif verbose:
		print_mandatory_fields(doctype)


def make_test_objects(doctype, test_records, verbose=None):
	records = []
		
	for doclist in test_records:
		if "doctype" not in doclist[0]:
			doclist[0]["doctype"] = doctype
		d = webnotes.bean(copy=doclist)
		
		if webnotes.test_objects.get(d.doc.doctype):
			# do not create test records, if already exists
			return []
		if has_field(d.doc.doctype, "naming_series"):
			if not d.doc.naming_series:
				d.doc.naming_series = "_T-" + d.doc.doctype + "-"

		# submit if docstatus is set to 1 for test record
		docstatus = d.doc.docstatus
		
		d.doc.docstatus = 0
		d.insert()

		if docstatus == 1:
			d.submit()
		
		records.append(d.doc.name)
	return records

def print_mandatory_fields(doctype):
	print "Please setup make_test_records for: " + doctype
	print "-" * 60
	doctype_obj = webnotes.get_doctype(doctype)
	print "Autoname: " + (doctype_obj[0].autoname or "")
	print "Mandatory Fields: "
	for d in doctype_obj.get({"reqd":1}):
		print d.parent + ":" + d.fieldname + " | " + d.fieldtype + " | " + (d.options or "")
	print
	
def export_doc(doctype, docname):
	import json
	doclist = []
	ignore_list = ["name", "owner", "creation", "modified", "modified_by", "idx", "naming_series",
		"parenttype", "parent", "docstatus"]
	
	make_test_records(doctype)
	meta = webnotes.get_doctype(doctype)
	
	for d in webnotes.bean(doctype, docname):
		new_doc = {}
		for key, val in d.fields.iteritems():
			if val and key not in ignore_list:
				df = meta.get_field(key, d.parent or None, d.parentfield or None)
				if df and df.fieldtype == "Link":
					val = (webnotes.test_objects.get(df.options) or [val])[0]
				elif df and df.fieldtype == "Select" and df.options and df.options.startswith("link:"):
					val = (webnotes.test_objects.get(df.options[5:]) or [val])[0]
				if not df or df.reqd == 1:
					new_doc[key] = val
		doclist.append(new_doc)
		
	print json.dumps(doclist, indent=4, sort_keys=True).replace("    ", "\t")
		

def run_unittest(doctype, verbose=False):
	module = webnotes.conn.get_value("DocType", doctype, "module")
	test_module = get_module_name(doctype, module, "test_")
	make_test_records(doctype, verbose=verbose)

	try:
		exec ('from %s import *' % test_module) in globals()		
		del sys.argv[1:]
		unittest.main()
				
	except ImportError, e:
		print "No test module."
		
def run_all_tests(verbose):
	import os

	test_suite = unittest.TestSuite()
	for path, folders, files in os.walk("."):
		if 'locale' in folders: folders.remove('locale')
		# print path
		for filename in files:
			filename = cstr(filename)
			if filename.startswith("test_") and filename.endswith(".py"):
				# print filename[:-3]
				_run_test(path, filename, verbose, test_suite=test_suite, run=False)
				
				# webnotes.conn.rollback()
				# webnotes.test_objects = {}

	unittest.TextTestRunner(verbosity=1+(verbose and 1 or 0)).run(test_suite)

def _run_test(path, filename, verbose, test_suite=None, run=True):
	import os, imp
	from webnotes.modules.utils import peval_doclist
	
	if not test_suite:
		test_suite = unittest.TestSuite()
	
	if os.path.basename(os.path.dirname(path))=="doctype":
		txt_file = os.path.join(path, filename[5:].replace(".py", ".txt"))
		with open(txt_file, 'r') as f:
			doctype_doclist = peval_doclist(f.read())
		doctype = doctype_doclist[0]["name"]
		make_test_records(doctype, verbose)
	
	module = imp.load_source(filename[:-3], os.path.join(path, filename))
	test_suite.addTest(unittest.TestLoader().loadTestsFromModule(module))
	
	if run:
		unittest.TextTestRunner(verbosity=1+(verbose and 1 or 0)).run(test_suite)

def main():
	import argparse
	
	parser = argparse.ArgumentParser(description='Run tests.')
	parser.add_argument('-d', '--doctype', nargs=1, metavar = "DOCTYPE",
		help="test for doctype")
	parser.add_argument('-v', '--verbose', default=False, action="store_true")
	parser.add_argument('-e', '--export', nargs=2, metavar="DOCTYPE DOCNAME")
	parser.add_argument('-a', '--all', default=False, action="store_true")
	parser.add_argument('-m', '--module', default=1, metavar="MODULE")

	args = parser.parse_args()
	if not webnotes.conn:
		webnotes.connect()

	webnotes.flags.print_messages = args.verbose
	webnotes.flags.in_test = True
	
	if args.doctype:
		run_unittest(args.doctype[0], verbose=args.verbose)
	elif args.all:
		run_all_tests(args.verbose)
	elif args.export:
		export_doc(args.export[0], args.export[1])
	elif args.module:
		import importlib
		
		test_suite = unittest.TestSuite()
		module = importlib.import_module(args.module)
		if hasattr(module, "test_dependencies"):
			for doctype in module.test_dependencies:
				make_test_records(doctype, verbose=args.verbose)
		
		test_suite.addTest(unittest.TestLoader().loadTestsFromModule(sys.modules[args.module]))
		unittest.TextTestRunner(verbosity=1+(args.verbose and 1 or 0)).run(test_suite)

if __name__=="__main__":
	main()