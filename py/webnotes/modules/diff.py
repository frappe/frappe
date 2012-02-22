"""get diff bettween txt files and database records"""

import webnotes

dt_map = {
	'DocType': {
		'DocField': ['fieldname', 'label']
	},
	'Page': {}
}

ignore_fields = ('modified', 'creation', 'owner', 'modified_by', 
	'_last_update', 'version', 'idx', 'name')

missing = property_diff = 0
property_count = {}

def diff():
	"""get diff"""
	global missing, property_diff, property_count
	missing = property_diff = 0
	property_count = {}

	import os, webnotes.defs
	from webnotes.model.utils import peval_doclist
	
	for wt in os.walk(webnotes.defs.modules_path):
		for fname in wt[2]:
			if fname.endswith('.txt'):
				path = os.path.join(wt[0], fname)
				with open(path, 'r') as txtfile:
					doclist_diff(peval_doclist(txtfile.read()))
	
	print
	print "Missing records: " + str(missing)
	print "Property mismatch: " + str(property_diff)
	for key in property_count:
		print "- " + key + ": " + str(property_count[key] or 0)
	print

def doclist_diff(doclist):
	# main doc
	global missing

	doc = doclist[0]
	if doc['doctype'] in dt_map.keys():
		# do for main
		db_doc = webnotes.conn.sql("""select * from `tab%s` 
			where name=%s""" % (doc['doctype'], '%s'), doc['name'], as_dict=1)
		doc_diff(doc, db_doc)
		
		if not db_doc:
			missing += 1
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
					db_doc = webnotes.conn.sql("""select * from `tab%s`
						where `%s`=%s and parent=%s""" % (d['doctype'], child_key, '%s', '%s'),
						(child_key_value, d['parent']), as_dict=1)
					
					doc_diff(d, db_doc, child_key_value)
	

def doc_diff(doc, db_doc, child_key_value=None):
	from termcolor import colored
	global property_diff, property_count

	if doc.get('parent'):
		docname = doc.get('parent') + '.' + child_key_value
	else:
		docname = doc['name']
	
	if not db_doc:
		print(colored((doc['doctype'] + ' -> ' + docname), 'red') + ' missing')
	
	else:
		db_doc = db_doc[0]
		db_doc['doctype'] = doc['doctype']
		for key in doc:
			if (key not in ignore_fields) \
				and (db_doc.get(key) != doc[key]) \
				and (not (db_doc.get(key)==None and doc[key]==0)):
				
				prefix = doc['doctype']+' -> ' + docname + ' -> '+key+' = '
				in_db = colored(str(db_doc.get(key)), 'red')
				in_file = colored(str(doc[key]), 'green')
				
				print(prefix + in_db + ' | ' + in_file)
				
				property_diff += 1
				if not key in property_count:
					property_count[key] = 0
				property_count[key] += 1