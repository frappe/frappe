from __future__ import unicode_literals

import webnotes
import sys
from webnotes.model.meta import get_link_fields
from webnotes.model.code import load_doctype_module

test_objects = {}

def run_tests(doctype):
	load_test_objects(doctype)
	#clear_dependencies()
	
def load_test_objects(doctype):
	global test_objects
	
	for fieldname, options, label in get_link_fields(doctype):
		if options.startswith("link:"):
			options = options[5:]
		if options == "[Select]":
			continue
		if not options in test_objects:
			moduleobj = load_doctype_module(options, 
				webnotes.conn.get_value("DocType", options, "module"))
			if hasattr(moduleobj, "make_test_records"):
				test_objects[options] = moduleobj.make_test_records()
			elif hasattr(moduleobj, "test_records"):
				test_objects[options] = []
				for doclist in moduleobj.test_records:
					d = webnotes.model_wrapper(doclist)
					d.insert()
					test_objects[options].append(d.doc.name)
			else:
				test_objects[options] = []
				print "Please setup make_test_records for: " + options
			
			make_dependencies(options)

def clear_dependencies():
	global test_objects

	from webnotes.model.utils import delete_doc
	for doctype in test_objects:
		for name in test_objects[doctype]:
			delete_doc(doctype, name)
			
if __name__=="__main__":
	webnotes.connect()
	run_tests(sys.argv[1])
	
