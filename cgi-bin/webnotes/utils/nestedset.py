# Tree (Hierarchical) Nested Set Model (nsm)
# 
# To use the nested set model,
# use the following pattern
# 1. name your parent field as "parent_node" if not have a property nsm_parent_field as your field name in the document class
# 2. have a field called "old_parent" in your fields list - this identifies whether the parent has been changed
# 3. call update_nsm(doc_obj) in the on_upate method

# ------------------------------------------

import webnotes

# called in the on_update method
def update_nsm(doc_obj):
	# get fields, data from the DocType
	d = doc_obj.doc
	pf, opf = 'parent_node', 'old_parent'
	if hasattr(doc_obj,'nsm_parent_field'):
		pf = doc_obj.nsm_parent_field
	if hasattr(doc_obj,'nsm_oldparent_field'):
		opf = doc_obj.nsm_oldparent_field
	p, op = d.fields[pf], d.fields.get(opf, '')

	# has parent changed (?) or parent is None (root)
	if not doc_obj.doc.lft and not doc_obj.doc.rgt:
		update_add_node(doc_obj.doc.doctype, doc_obj.doc.name, p or '', pf)
	elif op != p:
		update_remove_node(doc_obj.doc.doctype, doc_obj.doc.name)
		update_add_node(doc_obj.doc.doctype, doc_obj.doc.name, p or '', pf)
	# set old parent
	webnotes.conn.set(d, opf, p or '')
	
def rebuild_tree(doctype, parent_field):
	# get all roots
	right = 1
	result = webnotes.conn.sql("SELECT name FROM `tab%s` WHERE `%s`='' or `%s` IS NULL" % (doctype, parent_field, parent_field))
	for r in result:
		right = rebuild_node(doctype, r[0], right, parent_field)
		
def rebuild_node(doctype, parent, left, parent_field):
	# the right value of this node is the left value + 1
	right = left+1

	# get all children of this node
	result = webnotes.conn.sql("SELECT name FROM `tab%s` WHERE `%s`='%s'" % (doctype, parent_field, parent))
	for r in result:
		right = rebuild_node(doctype, r[0], right, parent_field)

	# we've got the left value, and now that we've processed
	# the children of this node we also know the right value
	webnotes.conn.sql('UPDATE `tab%s` SET lft=%s, rgt=%s WHERE name="%s"' % (doctype,left,right,parent))

	#return the right value of this node + 1
	return right+1
	
def update_add_node(doctype, name, parent, parent_field):
	# get the last sibling of the parent
	if parent:
		right = webnotes.conn.sql("select rgt from `tab%s` where name='%s'" % (doctype, parent))[0][0]
	else: # root
		right = webnotes.conn.sql("select ifnull(max(rgt),0)+1 from `tab%s` where ifnull(`%s`,'') =''" % (doctype, parent_field))[0][0]
	right = right or 1
	
	# update all on the right
	webnotes.conn.sql("update `tab%s` set rgt = rgt+2 where rgt >= %s" %(doctype,right))
	webnotes.conn.sql("update `tab%s` set lft = lft+2 where lft >= %s" %(doctype,right))
	
	#$ update index of new node
	webnotes.conn.sql("update `tab%s` set lft=%s, rgt=%s where name='%s'" % (doctype,right,right+1,name))
	return right

def update_remove_node(doctype, name):
	left = webnotes.conn.sql("select lft from `tab%s` where name='%s'" % (doctype,name))
	if left[0][0]:
		# reset this node
		webnotes.conn.sql("update `tab%s` set lft=0, rgt=0 where name='%s'" % (doctype,name))

		# update all on the right
		webnotes.conn.sql("update `tab%s` set rgt = rgt-2 where rgt > %s" %(doctype,left[0][0]))
		webnotes.conn.sql("update `tab%s` set lft = lft-2 where lft > %s" %(doctype,left[0][0]))
