# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes

def get_mapped_doclist(from_doctype, from_docname, table_maps, target_doclist=[]):
	if not webnotes.has_permission(from_doctype, from_docname):
		webnotes.msgprint("No Permission", raise_exception=webnotes.PermissionError)

	from webnotes.model import default_fields
	source = webnotes.bean(from_doctype, from_docname)
		
	# main
	if target_doclist:
		target_doc = webnotes.doc(target_doclist[0])
	else:
		target_doc = webnotes.new_doc(table_maps[from_doctype]["doctype"])
	
	no_copy_fields = set(get_no_copy_fields(from_doctype) \
		+ get_no_copy_fields(table_maps[from_doctype]["doctype"]) \
		+ default_fields)

	# map same fields
	for key in target_doc.fields:
		if key not in no_copy_fields:
			val = source.doc.fields.get(key)
			if val not in (None, ""):
				target_doc.fields[key] = val

	# map other fields
	for source_key, target_key in table_maps[from_doctype].get("field_map", {}).items():
		val = source.doc.fields.get(source_key)
		if val not in (None, ""):
			target_doc.fields[target_key] = val

	return [target_doc]

def get_no_copy_fields(doctype):
	meta = webnotes.get_doctype(doctype)
	no_copy_fields = []
	for d in meta.get({"doctype":"DocField", "no_copy": 1}):
		no_copy_fields.append(d.fieldname)
		
	return no_copy_fields