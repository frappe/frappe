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
import webnotes, json
from webnotes import _
from webnotes.utils import cstr
from webnotes.model import default_fields

def get_mapped_doclist(from_doctype, from_docname, table_maps, target_doclist=[], postprocess=None):
	if isinstance(target_doclist, basestring):
		target_doclist = json.loads(target_doclist)
	
	if not webnotes.has_permission(from_doctype, from_docname):
		webnotes.msgprint("No Permission", raise_exception=webnotes.PermissionError)

	source = webnotes.bean(from_doctype, from_docname)

	source_meta = webnotes.get_doctype(from_doctype)
	target_meta = webnotes.get_doctype(table_maps[from_doctype]["doctype"])
	
	# main
	if target_doclist:
		target_doc = webnotes.doc(target_doclist[0])
	else:
		target_doc = webnotes.new_doc(table_maps[from_doctype]["doctype"])
	
	map_doc(source.doc, target_doc, table_maps[source.doc.doctype], source_meta, target_meta)
	doclist = [target_doc]

	# children
	for source_d in source.doclist[1:]:
		target_doctype = table_maps[source_d.doctype]["doctype"]
		parentfield = target_meta.get({
				"parent": target_doc.doctype, 
				"doctype": "DocField",
				"fieldtype": "Table", 
				"options": target_doctype
			})[0].fieldname
		
		target_d = webnotes.new_doc(target_doctype, target_doc, parentfield)
		map_doc(source_d, target_d, table_maps[source_d.doctype], source_meta, target_meta)
		doclist.append(target_d)
	
	if postprocess:
		postprocess(source, doclist)
	
	return doclist

def map_doc(source_doc, target_doc, table_map, source_meta, target_meta):
	no_copy_fields = set(\
		  [d.fieldname for d in source_meta.get({"no_copy": 1, 
			"parent": source_doc.doctype})] \
		+ [d.fieldname for d in target_meta.get({"no_copy": 1, 
			"parent": target_doc.doctype})] \
		+ default_fields)

	if table_map.get("validation"):
		for key, condition in table_map["validation"].items():
			if condition[0]=="=":
				if source_doc.fields.get(key) != condition[1]:
					webnotes.msgprint(_("Cannot map because following condition fails: ")
						+ key + "=" + cstr(condition[1]), raise_exception=webnotes.ValidationError)

	# map same fields
	target_fields = target_meta.get({"doctype": "DocField", "parent": target_doc.doctype})
	for key in [d.fieldname for d in target_fields]:
		if key not in no_copy_fields:
			val = source_doc.fields.get(key)
			if val not in (None, ""):
				target_doc.fields[key] = val
				

	# map other fields
	for source_key, target_key in table_map.get("field_map", {}).items():
		val = source_doc.fields.get(source_key)
		if val not in (None, ""):
			target_doc.fields[target_key] = val

	# map idx
	if source_doc.idx:
		target_doc.idx = source_doc.idx
		
	if "postprocess" in table_map:
		table_map["postprocess"](source_doc, target_doc)