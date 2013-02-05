from __future__ import unicode_literals

import webnotes
import sys
from webnotes.model.meta import get_link_fields
from webnotes.model.code import load_doctype_module

test_objects = {}
	
def make_test_records(doctype):
	global test_objects
	webnotes.mute_emails = True
	if not webnotes.conn:
		webnotes.connect()
	
	for fieldname, options, label in get_link_fields(doctype):
		if options.startswith("link:"):
			options = options[5:]
		if options == "[Select]":
			continue
		if not options in test_objects:
			test_objects[options] = []
			make_test_records(options)
			moduleobj = load_doctype_module(options, 
				webnotes.conn.get_value("DocType", options, "module"))

			if hasattr(moduleobj, "make_test_records"):
				test_objects[options] = moduleobj.make_test_records()

			elif hasattr(moduleobj, "test_records"):
				for doclist in moduleobj.test_records:
					d = webnotes.model_wrapper(doclist)
					d.insert()
					if not d.doc.doctype in test_objects:
						test_objects[d.doc.doctype] = []
					test_objects[d.doc.doctype].append(d.doc.name)

			else:
				print "Please setup make_test_records for: " + options
				print "-" * 60
				print_mandatory_fields(options)
				print

def print_mandatory_fields(doctype):
	doctype_obj = webnotes.get_doctype(doctype)
	print "Autoname: " + (doctype_obj[0].autoname or "")
	print "Mandatory Fields: "
	for d in doctype_obj.get({"reqd":1}):
		print d.parent + ":" + d.fieldname + " | " + d.fieldtype + " | " + (d.options or "")
			
if __name__=="__main__":
	sys.path.extend(["app", "lib"])
	webnotes.connect()
	make_test_records(sys.argv[1])
	
