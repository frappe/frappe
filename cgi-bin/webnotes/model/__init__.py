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
			item = sql("select name from `tab%s` where `%s`='%s' and docstatus!=2 limit 1" % (link_dt, link_field, dn))
			if item:
				webnotes.msgprint("Cannot delete %s <b>%s</b> because it is linked in %s <b>%s</b>" % (dt, dn, link_dt, item[0][0]), raise_exception=1)


def delete_doc(doctype=None, name=None, doclist = None):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	import webnotes.model.meta
	sql = webnotes.conn.sql

	# guest cannot delete
	if webnotes.user.name == 'Guest':
		webnotes.msgprint('Guest cannot call delete', raise_exception =1)

	# from form
	if not doctype:
		doctype = webnotes.form_dict.get('dt')
		name = webnotes.form_dict.get('dn')
		if not doctype:
			webnotes.msgprint('Nothing to delete!', raise_exception =1)

	# already deleted
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
	check_if_doc_is_linked(doctype, name)
	
	try:
		webnotes.conn.sql("delete from `tab%s` where name='%s' limit 1" % (doctype, name))
		for t in tablefields:
			webnotes.conn.sql("delete from `tab%s` where parent = %s" % (t[0], '%s'), name)
	except Exception, e:
		if e.args[0]==1451:
			webnotes.msgprint("Cannot delete %s '%s' as it is referenced in another record. You must delete the referred record first" % (doctype, name))
		
		raise e
	
	return 'okay'

#=================================================================================
# new feature added 9-Jun-10 to allow doctypes to have labels 
def get_dt_labels():
	d = {}
	try:
		res = webnotes.conn.sql("select name, dt_label from `tabDocType Label`")
	except:
		return {}
		
	for r in res:
		d[r[0]] = r[1]
	
	return d
#=================================================================================

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
	sql = webnotes.conn.sql

	# rename doc
	sql("update `tab%s` set name='%s' where name='%s'" % (dt, new, old))

	# get child docs
	ct = sql("select options from tabDocField where parent = '%s' and fieldtype='Table'" % dt)
	for c in ct:
		sql("update `tab%s` set parent='%s' where parent='%s'" % (c[0], new, old))

	# get links (link / select)
	ll = get_link_fields(dt)
	for l in ll:
		is_single = sql("select issingle from tabDocType where name = '%s'" % l[0])
		is_single = is_single and webnotes.utils.cint(is_single[0][0]) or 0
		if is_single:
			sql("update `tabSingles` set value='%s' where field='%s' and value = '%s' and doctype = '%s' " % (new, l[1], old, l[0]))
		else:
			sql("update `tab%s` set `%s`='%s' where `%s`='%s'" % (l[0], l[1], new, l[1], old))

	# doctype
	if is_doctype:
		sql("RENAME TABLE `tab%s` TO `tab%s`" % (old, new))

		# get child docs (update parenttype)
		ct = sql("select options from tabDocField where parent = '%s' and fieldtype='Table'" % new)
		for c in ct:
			sql("update `tab%s` set parenttype='%s' where parenttype='%s'" % (c[0], new, old))

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
