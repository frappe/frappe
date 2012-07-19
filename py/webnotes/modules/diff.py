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
"""get diff bettween txt files and database records"""

import webnotes
import os, conf
from webnotes.model.utils import peval_doclist

dt_map = {
	'DocType': {
		'DocField': ['fieldname', 'label']
	},
	'Search Criteria': {},
	'Page': {}
}

ignore_fields = ('modified', 'creation', 'owner', 'modified_by', 
	'_last_update', 'version', 'idx', 'name')

missing = property_diff = 0
property_count = {}


def diff_ref_file():
	"""get diff using .txt files as reference"""
	global missing, property_diff, property_count
	missing = property_diff = 0
	property_count = {}

	get_diff(conf.modules_path)
	get_diff(os.path.join(os.getcwd(), 'lib', 'py', 'core'))
	
	print_stats()


def get_diff(path):
	for wt in os.walk(path):
		for fname in wt[2]:
			if fname.endswith('.txt'):
				path = os.path.join(wt[0], fname)
				with open(path, 'r') as txtfile:
					doclist_diff(peval_doclist(txtfile.read()))

	
def diff_ref_db():
	"""get diff using database as reference"""
	from webnotes.modules import scrub
	for dt in dt_map:
		# get all main docs
		for doc in webnotes.conn.sql("""select * from `tab%s`""" % dt, as_dict=1):
			# get file for this doc
			doc['doctype'] = dt
			#print doc['name'], doc['doctype'], doc['module']
			path = os.path.join(conf.modules_path, scrub(doc['module']), \
				scrub(dt), scrub(doc['name']), scrub(doc['name']) + '.txt')	
			path_core = os.path.join(os.getcwd(), 'lib', 'py', 'core', \
				scrub(dt), scrub(doc['name']), scrub(doc['name']) + '.txt')

			if os.path.exists(path):
				with open(path, 'r') as txtfile:
					target = peval_doclist(txtfile.read())					
			elif os.path.exists(path_core):
				with open(path_core, 'r') as txtfile:
					target = peval_doclist(txtfile.read())					
			else:
				target = [None,]
			
			doc_diff(doc, target[0])
			
			# do diff for child records
			if target[0] and dt_map[dt].keys():
				for child_dt in dt_map[dt]:					

					# for each child type, we need to create
					# a key (e.g. fieldname, label) based mapping of child records in 
					# txt files
					child_key_map = {}
					keys = dt_map[dt][child_dt]
					for target_d in target:
						if target_d['doctype'] == child_dt:
							for key in keys:
								if target_d.get(key):
									child_key_map[target_d.get(key)] = target_d
									break

					for d in webnotes.conn.sql("""select * from `tab%s` where 
						parent=%s and docstatus<2""" % (child_dt, '%s'), doc['name'], as_dict=1):

						source_key = None
						d['doctype'] = child_dt
						for key in keys:
							if d.get(key):
								source_key = d.get(key)
								break
						
						# only if a key is found
						if source_key:
							doc_diff(d, child_key_map.get(source_key), source_key)
				

	print_stats()


def doclist_diff(doclist):
	# main doc
	doc = doclist[0]
	if doc['doctype'] in dt_map.keys():
		# do for main
		target = webnotes.conn.sql("""select * from `tab%s` 
			where name=%s""" % (doc['doctype'], '%s'), doc['name'], as_dict=1)
		doc_diff(doc, target and target[0] or None)
		
		if not target:
			# no parent, no children!
			return
			
		for d in doclist[1:]:
			# if child
			if d['doctype'] in dt_map[doc['doctype']].keys():
				child_keys = dt_map[doc['doctype']][d['doctype']]
				
				# find the key on which a child is unique
				child_key = child_key_value = None
				for key in child_keys:
					if d.get(key):
						child_key = key
						child_key_value = d[key]
						break
					
				# incoming child record has a uniquely
				# identifiable key
				if child_key:
					target = webnotes.conn.sql("""select * from `tab%s`
						where `%s`=%s and parent=%s""" % (d['doctype'], child_key, '%s', '%s'),
						(child_key_value, d['parent']), as_dict=1)
					
					doc_diff(d, target and target[0] or None, child_key_value)
	

def doc_diff(source, target, child_key_value=None):
	from termcolor import colored
	global property_diff, property_count, missing

	docname = source.get('parent') and (source.get('parent') + '.' + child_key_value) \
		or source['name']

	if not target:
		missing += 1
		print(colored((source['doctype'] + ' -> ' + docname), 'red') + ' missing')
		
	else:
		target['doctype'] = source['doctype']
		for key in source:
			if (key not in ignore_fields) \
				and (target.get(key) != source[key]) \
				and (not (target.get(key)==None and source[key]==0)):
				
				prefix = source['doctype']+' -> ' + docname + ' -> '+key+' = '
				in_db = colored(str(target.get(key)), 'red')
				in_file = colored(str(source[key]), 'green')
				
				print(prefix + in_db + ' | ' + in_file)
				
				property_diff += 1
				if not key in property_count:
					property_count[key] = 0
				property_count[key] += 1
				
def print_stats():
	print
	print "Missing records: " + str(missing)
	print "Property mismatch: " + str(property_diff)
	for key in property_count:
		print "- " + key + ": " + str(property_count[key] or 0)
	print
