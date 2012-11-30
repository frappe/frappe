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

from __future__ import unicode_literals

def insert_test_data(doctype, sort_fn=None):
	import webnotes.model
	data = get_test_doclist(doctype)
	if sort_fn:
		data = sorted(data, key=sort_fn)

	for doclist in data:
		webnotes.insert(doclist)

def get_test_doclist(doctype, name=None):
	"""get test doclist, collection of doclists"""
	import os, conf, webnotes
	from webnotes.modules.utils import peval_doclist
	from webnotes.modules import scrub

	doctype = scrub(doctype)
	doctype_path = os.path.join(os.path.dirname(os.path.abspath(conf.__file__)),
		conf.test_data_path, doctype)
	
	if name:
		with open(os.path.join(doctype_path, scrub(name) + '.txt'), 'r') as txtfile:
			doclist = peval_doclist(txtfile.read())

		return doclist
		
	else:
		all_doclists = []
		for fname in filter(lambda n: n.endswith('.txt'), os.listdir(doctype_path)):
			with open(os.path.join(doctype_path, scrub(fname)), 'r') as txtfile:
				all_doclists.append(peval_doclist(txtfile.read()))
		
		return all_doclists
