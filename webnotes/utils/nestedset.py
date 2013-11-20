# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

# Tree (Hierarchical) Nested Set Model (nsm)
# 
# To use the nested set model,
# use the following pattern
# 1. name your parent field as "parent_item_group" if not have a property nsm_parent_field as your field name in the document class
# 2. have a field called "old_parent" in your fields list - this identifies whether the parent has been changed
# 3. call update_nsm(doc_obj) in the on_upate method

# ------------------------------------------
from __future__ import unicode_literals

import webnotes
from webnotes import msgprint, _
from webnotes.model.bean import Bean
from webnotes.model.doc import Document

# called in the on_update method
def update_nsm(doc_obj):
	# get fields, data from the DocType
	
	pf, opf = 'parent_node', 'old_parent'

	if str(doc_obj.__class__)=='webnotes.model.doc.Document':
		# passed as a Document object
		d = doc_obj
	else:
		# passed as a DocType object
		d = doc_obj.doc
	
		if hasattr(doc_obj,'nsm_parent_field'):
			pf = doc_obj.nsm_parent_field
		if hasattr(doc_obj,'nsm_oldparent_field'):
			opf = doc_obj.nsm_oldparent_field

	p, op = d.fields.get(pf, ''), d.fields.get(opf, '')
	
	# has parent changed (?) or parent is None (root)
	if not d.lft and not d.rgt:
		update_add_node(d, p or '', pf)
	elif op != p:
		update_move_node(d, pf)

	# set old parent
	d.fields[opf] = p
	webnotes.conn.set_value(d.doctype, d.name, opf, p or '')

	# reload
	d._loadfromdb()

def update_add_node(doc, parent, parent_field):
	"""
		insert a new node
	"""
	from webnotes.utils import now
	n = now()
	
	doctype = doc.doctype
	name = doc.name

	# get the last sibling of the parent
	if parent:
		left, right = webnotes.conn.sql("select lft, rgt from `tab%s` where name=%s" \
			% (doctype, "%s"), parent)[0]
		validate_loop(doc.doctype, doc.name, left, right)
	else: # root
		right = webnotes.conn.sql("select ifnull(max(rgt),0)+1 from `tab%s` where ifnull(`%s`,'') =''" % (doctype, parent_field))[0][0]
	right = right or 1
		
	# update all on the right
	webnotes.conn.sql("update `tab%s` set rgt = rgt+2, modified='%s' where rgt >= %s" %(doctype,n,right))
	webnotes.conn.sql("update `tab%s` set lft = lft+2, modified='%s' where lft >= %s" %(doctype,n,right))
	
	# update index of new node
	if webnotes.conn.sql("select * from `tab%s` where lft=%s or rgt=%s"% (doctype, right, right+1)):
		webnotes.msgprint("Nested set error. Please send mail to support")
		raise Exception

	webnotes.conn.sql("update `tab%s` set lft=%s, rgt=%s, modified='%s' where name='%s'" % (doctype,right,right+1,n,name))
	return right


def update_move_node(doc, parent_field):
	parent = doc.fields.get(parent_field)
	
	if parent:
		new_parent = webnotes.conn.sql("""select lft, rgt from `tab%s` 
			where name = %s""" % (doc.doctype, '%s'), parent, as_dict=1)[0]
		
		validate_loop(doc.doctype, doc.name, new_parent.lft, new_parent.rgt)
		
	# move to dark side
	webnotes.conn.sql("""update `tab%s` set lft = -lft, rgt = -rgt 
		where lft >= %s and rgt <= %s"""% (doc.doctype, '%s', '%s'), (doc.lft, doc.rgt))
				
	# shift left
	diff = doc.rgt - doc.lft + 1
	webnotes.conn.sql("""update `tab%s` set lft = lft -%s, rgt = rgt - %s 
		where lft > %s"""% (doc.doctype, '%s', '%s', '%s'), (diff, diff, doc.rgt))

	# shift left rgts of ancestors whose only rgts must shift
	webnotes.conn.sql("""update `tab%s` set rgt = rgt - %s 
		where lft < %s and rgt > %s"""% (doc.doctype, '%s', '%s', '%s'), 
		(diff, doc.lft, doc.rgt))
		
	if parent:
		new_parent = webnotes.conn.sql("""select lft, rgt from `tab%s` 
			where name = %s""" % (doc.doctype, '%s'), parent, as_dict=1)[0]
	
	
		# set parent lft, rgt
		webnotes.conn.sql("""update `tab%s` set rgt = rgt + %s 
			where name = %s"""% (doc.doctype, '%s', '%s'), (diff, parent))
		
		# shift right at new parent
		webnotes.conn.sql("""update `tab%s` set lft = lft + %s, rgt = rgt + %s 
			where lft > %s""" % (doc.doctype, '%s', '%s', '%s'), 
			(diff, diff, new_parent.rgt))

		# shift right rgts of ancestors whose only rgts must shift
		webnotes.conn.sql("""update `tab%s` set rgt = rgt + %s 
			where lft < %s and rgt > %s""" % (doc.doctype, '%s', '%s', '%s'), 
			(diff, new_parent.lft, new_parent.rgt))

			
		new_diff = new_parent.rgt - doc.lft
	else:
		# new root
		max_rgt = webnotes.conn.sql("""select max(rgt) from `tab%s`""" % doc.doctype)[0][0]
		new_diff = max_rgt + 1 - doc.lft
		
	# bring back from dark side	
	webnotes.conn.sql("""update `tab%s` set lft = -lft + %s, rgt = -rgt + %s 
		where lft < 0"""% (doc.doctype, '%s', '%s'), (new_diff, new_diff))
		
def rebuild_tree(doctype, parent_field):
	"""
		call rebuild_node for all root nodes
	"""
	# get all roots
	webnotes.conn.auto_commit_on_many_writes = 1

	right = 1
	result = webnotes.conn.sql("SELECT name FROM `tab%s` WHERE `%s`='' or `%s` IS NULL ORDER BY name ASC" % (doctype, parent_field, parent_field))
	for r in result:
		right = rebuild_node(doctype, r[0], right, parent_field)

	webnotes.conn.auto_commit_on_many_writes = 0
		
def rebuild_node(doctype, parent, left, parent_field):
	"""
		reset lft, rgt and recursive call for all children
	"""
	from webnotes.utils import now
	n = now()

	# the right value of this node is the left value + 1
	right = left+1	

	# get all children of this node
	result = webnotes.conn.sql("SELECT name FROM `tab%s` WHERE `%s`='%s'" % (doctype, parent_field, parent))
	for r in result:
		right = rebuild_node(doctype, r[0], right, parent_field)

	# we've got the left value, and now that we've processed
	# the children of this node we also know the right value
	webnotes.conn.sql("UPDATE `tab%s` SET lft=%s, rgt=%s, modified='%s' WHERE name='%s'" % (doctype,left,right,n,parent))

	#return the right value of this node + 1
	return right+1
	

def validate_loop(doctype, name, lft, rgt):
	"""check if item not an ancestor (loop)"""
	if name in webnotes.conn.sql_list("""select name from `tab%s` where lft <= %s and rgt >= %s""" % (doctype, 
		"%s", "%s"), (lft, rgt)):
		webnotes.throw("""Item cannot be added to its own descendents.""")

class DocTypeNestedSet(object):
	def on_update(self):
		update_nsm(self)
		self.validate_ledger()
		
	def on_trash(self):
		parent = self.doc.fields[self.nsm_parent_field]
		if not parent:
			msgprint(_("Root ") + self.doc.doctype + _(" cannot be deleted."), raise_exception=1)

		self.doc.fields[self.nsm_parent_field] = ""
		update_nsm(self)
		
	def on_rename(self, newdn, olddn, merge=False, group_fname="is_group"):
		if merge:
			is_group = webnotes.conn.get_value(self.doc.doctype, newdn, group_fname)
			if self.doc.fields[group_fname] != is_group:
				msgprint(_("""Merging is only possible between Group-to-Group or 
					Ledger-to-Ledger"""), raise_exception=1)
				
			parent_field = "parent_" + self.doc.doctype.replace(" ", "_").lower()
			rebuild_tree(self.doc.doctype, parent_field)
		
	def validate_one_root(self):
		if not self.doc.fields[self.nsm_parent_field]:
			if webnotes.conn.sql("""select count(*) from `tab%s` where
				ifnull(%s, '')=''""" % (self.doc.doctype, self.nsm_parent_field))[0][0] > 1:
				webnotes.throw(_("""Multiple root nodes not allowed."""))

	def validate_ledger(self, group_identifier="is_group"):
		if self.doc.fields.get(group_identifier) == "No":
			if webnotes.conn.sql("""select name from `tab%s` where %s=%s and docstatus!=2""" % 
				(self.doc.doctype, self.nsm_parent_field, '%s'), (self.doc.name)):
					webnotes.throw(self.doc.doctype + ": " + self.doc.name + 
						_(" can not be marked as a ledger as it has existing child"))
				