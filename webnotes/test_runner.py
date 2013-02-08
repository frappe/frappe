from __future__ import unicode_literals

import sys
if __name__=="__main__":
	sys.path.extend([".", "app", "lib"])

import webnotes
from webnotes.model.meta import get_link_fields
from webnotes.model.code import load_doctype_module

def make_test_records(doctype, verbose=0):
	webnotes.mute_emails = True
	if not webnotes.conn:
		webnotes.connect()
	
	# also include doctype itself
	options_list = list(set([options for fieldname, options, label 
		in get_link_fields(doctype)] + [doctype]))
		
	for options in options_list:
		if options.startswith("link:"):
			options = options[5:]
		if options == "[Select]":
			continue
		
		if options not in webnotes.test_objects:
			webnotes.test_objects[options] = []
			make_test_records(options, verbose)
			
			load_module_and_make_records(options, verbose)
			
def load_module_and_make_records(options, verbose=0):
	module = webnotes.conn.get_value("DocType", options, "module")

	# get methods for either [doctype].py or test_[doctype].py
	doctype_module = load_doctype_module(options, module)
	test_module = load_doctype_module(options, module, "test_")

	if hasattr(test_module, "make_test_records"):
		webnotes.test_objects[options] += test_module.make_test_records(verbose)

	elif hasattr(doctype_module, "make_test_records"):
		webnotes.test_objects[options] += doctype_module.make_test_records(verbose)

	elif hasattr(test_module, "test_records"):
		webnotes.test_objects[options] += make_test_objects(test_module)

	elif hasattr(doctype_module, "test_records"):
		webnotes.test_objects[options] += make_test_objects(doctype_module)

	elif verbose:
		print_mandatory_fields(options)

def make_test_objects(obj):
	if isinstance(obj, list):
		test_records = obj
	else:
		# obj is a module object
		test_records = obj.test_records
		
	records = []
	for doclist in test_records:
		d = webnotes.model_wrapper((webnotes.doclist(doclist)).copy())
		if webnotes.test_objects.get(d.doc.doctype):
			# do not create test records, if already exists
			return []
		d.insert()
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

if __name__=="__main__":
	make_test_records(sys.argv[1], verbose=1)
	
