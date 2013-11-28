# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

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
	import os, webnotes
	from webnotes import conf
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
