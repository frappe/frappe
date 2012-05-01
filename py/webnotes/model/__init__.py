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

# model __init__.py
import webnotes

no_value_fields = ['Section Break', 'Column Break', 'HTML', 'Table', 'FlexTable', 'Button', 'Image', 'Graph']
default_fields = ['doctype','name','owner','creation','modified','modified_by','parent','parentfield','parenttype','idx','docstatus']

#=================================================================================

def check_if_doc_is_linked(dt, dn):
	"""
		Raises excption if the given doc(dt, dn) is linked in another record.
	"""
	sql = webnotes.conn.sql

	ll = get_link_fields(dt)
	for l in ll:
		link_dt, link_field = l
		issingle = sql("select issingle from tabDocType where name = '%s'" % link_dt)

		# no such doctype (?)
		if not issingle: continue
		
		if issingle[0][0]:
			item = sql("select doctype from `tabSingles` where field='%s' and value = '%s' and doctype = '%s' " % (link_field, dn, l[0]))
			if item:
				webnotes.msgprint("Cannot delete %s <b>%s</b> because it is linked in <b>%s</b>" % (dt, dn, item[0][0]), raise_exception=1)
			
		else:
			item = None
			try:
				item = sql("select name, parent, parenttype from `tab%s` where `%s`='%s' and docstatus!=2 limit 1" % (link_dt, link_field, dn))
			except Exception, e:
				if e.args[0]==1146: pass
				else: raise e
			if item:
				webnotes.msgprint("Cannot delete %s <b>%s</b> because it is linked in %s <b>%s</b>" % (dt, dn, item[0][2] or link_dt, item[0][1] or item[0][0]), raise_exception=1)

@webnotes.whitelist()
def delete_doc(doctype=None, name=None, doclist = None, force=0):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	import webnotes.model.meta
	sql = webnotes.conn.sql

	# get from form
	if not doctype:
		doctype = webnotes.form_dict.get('dt')
		name = webnotes.form_dict.get('dn')
	
	if not doctype:
		webnotes.msgprint('Nothing to delete!', raise_exception =1)

	# already deleted..?
	if not webnotes.conn.exists(doctype, name):
		return

	tablefields = webnotes.model.meta.get_table_fields(doctype)
	
	# check if submitted
	d = webnotes.conn.sql("select docstatus from `tab%s` where name=%s" % (doctype, '%s'), name)
	if d and int(d[0][0]) == 1:
		webnotes.msgprint("Submitted Record '%s' '%s' cannot be deleted" % (doctype, name))
		raise Exception
	
	# call on_trash if required
	from webnotes.model.code import get_obj
	if doclist:
		obj = get_obj(doclist=doclist)
	else:
		obj = get_obj(doctype, name)

	if hasattr(obj,'on_trash'):
		obj.on_trash()
	
	# check if links exist
	if not force:
		check_if_doc_is_linked(doctype, name)

	# remove tags
	from webnotes.widgets.tags import clear_tags
	clear_tags(doctype, name)
	
	try:
		webnotes.conn.sql("delete from `tab%s` where name='%s' limit 1" % (doctype, name))
		for t in tablefields:
			webnotes.conn.sql("delete from `tab%s` where parent = %s" % (t[0], '%s'), name)
	except Exception, e:
		if e.args[0]==1451:
			webnotes.msgprint("Cannot delete %s '%s' as it is referenced in another record. You must delete the referred record first" % (doctype, name))
		
		raise e
		
	return 'okay'

def get_search_criteria(dt):
	import webnotes.model.doc
	# load search criteria for reports (all)
	dl = []
	try: # bc
		sc_list = webnotes.conn.sql("select name from `tabSearch Criteria` where doc_type = '%s' or parent_doc_type = '%s' and (disabled!=1 OR disabled IS NULL)" % (dt, dt))
		for sc in sc_list:
			dl += webnotes.model.doc.get('Search Criteria', sc[0])
	except Exception, e:
		pass # no search criteria
	return dl


# Rename Doc
#=================================================================================

def get_link_fields(dt):
	"""
		Returns linked fields for dt as a tuple of (linked_doctype, linked_field)
	"""
	return webnotes.conn.sql("select parent, fieldname from tabDocField where parent not like 'old%%' and ((options = '%s' and fieldtype='Link') or (options = 'link:%s' and fieldtype='Select'))" % (dt, dt))

def rename(dt, old, new, is_doctype = 0):
	"""
		Renames a doc(dt, old) to doc(dt, new) and updates all linked fields of type "Link" or "Select" with "link:"
	"""
	import webnotes.utils

	sql = webnotes.conn.sql
	# rename doc
	sql("update `tab%s` set name='%s' where name='%s'" % (dt, new, old))

	# get child docs
	ct = sql("select options from tabDocField where parent = '%s' and fieldtype='Table'" % dt)
	for c in ct:
		sql("update `tab%s` set parent='%s' where parent='%s'" % (c[0], new, old))
	
	# if dt is a child table of another dt
	sql("update `tabDocField` set options = '%s' where options = '%s' and fieldtype = 'Table'" % (new, old))

	# get links (link / select)
	ll = get_link_fields(dt)
	update_link_fld_values(ll, old, new)


	# doctype
	if is_doctype:		
		# update options and values where select options contains old dt
		select_flds = sql("select parent, fieldname from `tabDocField` where parent not like 'old%%' and (options like '%%%s%%' or options like '%%%s%%') and options not like 'link:%%' and fieldtype = 'Select' and parent != '%s'" % ('\n' + old, old + '\n', new))
		update_link_fld_values(select_flds, old, new)
	
		sql("update `tabDocField` set options = replace(options, '%s', '%s') where (options like '%%%s%%' or options like '%%%s%%')" % (old, new, '\n' + old, old + '\n'))

		if not is_single_dt(old):
			sql("RENAME TABLE `tab%s` TO `tab%s`" % (old, new))
		else:
			sql("update tabSingles set doctype = %s where doctype = %s", (new, old))

		# get child docs (update parenttype)
		ct = sql("select options from tabDocField where parent = '%s' and fieldtype='Table'" % new)
		for c in ct:
			sql("update `tab%s` set parenttype='%s' where parenttype='%s'" % (c[0], new, old))



def update_link_fld_values(flds, old, new):
	for l in flds:
		if is_single_dt(l[0]):
			webnotes.conn.sql("update `tabSingles` set value='%s' where field='%s' and value = '%s' and doctype = '%s' " % (new, l[1], old, l[0]))
		else:
			webnotes.conn.sql("update `tab%s` set `%s`='%s' where `%s`='%s'" % (l[0], l[1], new, l[1], old))

def is_single_dt(dt):
	is_single = webnotes.conn.sql("select issingle from tabDocType where name = '%s'" % dt)
	is_single = is_single and webnotes.utils.cint(is_single[0][0]) or 0
	return is_single

#=================================================================================

def clear_recycle_bin():
	"""
		Clears temporary records that have been deleted
	"""
	sql = webnotes.conn.sql

	tl = sql('show tables')
	total_deleted = 0
	for t in tl:
		fl = [i[0] for i in sql('desc `%s`' % t[0])]
		
		if 'name' in fl:
			total_deleted += sql("select count(*) from `%s` where name like '__overwritten:%%'" % t[0])[0][0]
			sql("delete from `%s` where name like '__overwritten:%%'" % t[0])

		if 'parent' in fl:	
			total_deleted += sql("select count(*) from `%s` where parent like '__oldparent:%%'" % t[0])[0][0]
			sql("delete from `%s` where parent like '__oldparent:%%'" % t[0])
	
			total_deleted += sql("select count(*) from `%s` where parent like 'oldparent:%%'" % t[0])[0][0]
			sql("delete from `%s` where parent like 'oldparent:%%'" % t[0])

			total_deleted += sql("select count(*) from `%s` where parent like 'old_parent:%%'" % t[0])[0][0]
			sql("delete from `%s` where parent like 'old_parent:%%'" % t[0])

	webnotes.msgprint("%s records deleted" % str(int(total_deleted)))
	
	
# Make Table Copy
#=================================================================================

def copytables(srctype, src, srcfield, tartype, tar, tarfield, srcfields, tarfields=[]):
	import webnotes.model.doc

	if not tarfields: 
		tarfields = srcfields
	l = []
	data = webnotes.model.doc.getchildren(src.name, srctype, srcfield)
	for d in data:
		newrow = webnotes.model.doc.addchild(tar, tarfield, tartype, local = 1)
		newrow.idx = d.idx
	
		for i in range(len(srcfields)):
			newrow.fields[tarfields[i]] = d.fields[srcfields[i]]
			
		l.append(newrow)
	return l

# DB Exists
#=================================================================================

def db_exists(dt, dn):
	import webnotes
	return webnotes.conn.exists(dt, dn)


def delete_fields(args_dict, delete=0):
	"""
		Delete a field.
		* Deletes record from `tabDocField`
		* If not single doctype: Drops column from table
		* If single, deletes record from `tabSingles`

		args_dict = { dt: [field names] }
	"""
	import webnotes.utils
	for dt in args_dict.keys():
		fields = args_dict[dt]
		if not fields: continue
		
		webnotes.conn.sql("""\
			DELETE FROM `tabDocField`
			WHERE parent=%s AND fieldname IN (%s)
		""" % ('%s', ", ".join(['"' + f + '"' for f in fields])), dt)
		
		# Delete the data / column only if delete is specified
		if not delete: continue
		
		is_single = webnotes.conn.sql("select issingle from tabDocType where name = '%s'" % dt)
		is_single = is_single and webnotes.utils.cint(is_single[0][0]) or 0
		if is_single:
			webnotes.conn.sql("""\
				DELETE FROM `tabSingles`
				WHERE doctype=%s AND field IN (%s)
			""" % ('%s', ", ".join(['"' + f + '"' for f in fields])), dt)
		else:
			existing_fields = webnotes.conn.sql("desc `tab%s`" % dt)
			existing_fields = existing_fields and [e[0] for e in existing_fields] or []
			query = "ALTER TABLE `tab%s` " % dt + \
				", ".join(["DROP COLUMN `%s`" % f for f in fields if f in existing_fields])
			webnotes.conn.commit()
			webnotes.conn.sql(query)
				
			
