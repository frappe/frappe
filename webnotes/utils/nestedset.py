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

# Tree (Hierarchical) Nested Set Model (nsm)
# 
# To use the nested set model,
# use the following pattern
# 1. name your parent field as "parent_item_group" if not have a property nsm_parent_field as your field name in the document class
# 2. have a field called "old_parent" in your fields list - this identifies whether the parent has been changed
# 3. call update_nsm(doc_obj) in the on_upate method

# ------------------------------------------
from __future__ import unicode_literals

import webnotes, unittest
from webnotes import msgprint
from webnotes.model.wrapper import ModelWrapper
from webnotes.model.doc import Document

class TestNSM(unittest.TestCase):
	def setUp(self):
		webnotes.conn.sql("delete from `tabItem Group`")
		self.data = [
			["t1", None, 1, 20], 
				["c0", "t1", 2, 3],
				["c1", "t1", 4, 11],
					["gc1", "c1", 5, 6],
					["gc2", "c1", 7, 8],
					["gc3", "c1", 9, 10],
				["c2", "t1", 12, 17],
					["gc4", "c2", 13, 14],
					["gc5", "c2", 15, 16],
				["c3", "t1", 18, 19]
		]
		
		for d in self.data:
			self.__dict__[d[0]] = ModelWrapper([Document(fielddata = {
				"doctype": "Item Group", "item_group_name": d[0], "parent_item_group": d[1],
				"__islocal": 1
			})])
			
		self.save_all()
		self.reload_all()

	def save_all(self):
		for d in self.data:
			self.__dict__[d[0]].save()

	def reload_all(self, data=None):
		for d in data or self.data:
			self.__dict__[d[0]].load_from_db()
			
	def test_basic_tree(self, data=None):
		for d in data or self.data:
			self.assertEquals(self.__dict__[d[0]].doc.lft, d[2])
			self.assertEquals(self.__dict__[d[0]].doc.rgt, d[3])
			
	def test_move_group(self):
		self.c1.doc.parent_item_group = 'c2'
		self.c1.save()
		self.reload_all()
		
		new_tree = [
			["t1", None, 1, 20], 
				["c0", "t1", 2, 3],
				["c2", "t1", 4, 17],
					["gc4", "c2", 5, 6],
					["gc5", "c2", 7, 8],
					["c1", "t1", 9, 16],
						["gc1", "c1", 10, 11],
						["gc2", "c1", 12, 13],
						["gc3", "c1", 14, 15],
				["c3", "t1", 18, 19]
		]
		self.test_basic_tree(new_tree)
		
		# Move back
		
		self.c1.doc.parent_item_group = 'gc4'
		self.c1.save()
		self.reload_all()
		
		new_tree = [
			["t1", None, 1, 20], 
				["c0", "t1", 2, 3],
				["c2", "t1", 4, 17],
					["gc4", "c2", 5, 14],
						["c1", "t1", 6, 13],
							["gc1", "c1", 7, 8],
							["gc2", "c1", 9, 10],
							["gc3", "c1", 11, 12],
					["gc5", "c2", 15, 16],
				["c3", "t1", 18, 19]
		]
		self.test_basic_tree(new_tree)

		# Move to root
		
		self.c1.doc.parent_item_group = ''
		self.c1.save()
		self.reload_all()
		
		new_tree = [
			["t1", None, 1, 12],
				["c0", "t1", 2, 3],
				["c2", "t1", 4, 9],
					["gc4", "c2", 5, 6],
					["gc5", "c2", 7, 8],
				["c3", "t1", 10, 11],
			["c1", "t1", 13, 20],
				["gc1", "c1", 14, 15],
				["gc2", "c1", 16, 17],
				["gc3", "c1", 18, 19],
		]
		self.test_basic_tree(new_tree)
		
		# move leaf
		self.gc3.doc.parent_item_group = 'c2'
		self.gc3.save()
		self.reload_all()
		
		new_tree = [
			["t1", None, 1, 14],
				["c0", "t1", 2, 3],
				["c2", "t1", 4, 11],
					["gc4", "c2", 5, 6],
					["gc5", "c2", 7, 8],
					["gc3", "c1", 9, 10],
				["c3", "t1", 12, 13],
			["c1", "t1", 15, 20],
				["gc1", "c1", 16, 17],
				["gc2", "c1", 18, 19],
		]
		self.test_basic_tree(new_tree)
		
		# delete leaf
		from webnotes.model import delete_doc
		delete_doc(self.gc2.doc.doctype, self.gc2.doc.name)
		
		new_tree = [
			["t1", None, 1, 14],
				["c0", "t1", 2, 3],
				["c2", "t1", 4, 11],
					["gc4", "c2", 5, 6],
					["gc5", "c2", 7, 8],
					["gc3", "c1", 9, 10],
				["c3", "t1", 12, 13],
			["c1", "t1", 15, 18],
				["gc1", "c1", 16, 17],
		]
		
		del self.__dict__["gc2"]
		self.reload_all(new_tree)
		self.test_basic_tree(new_tree)

		# for testing
		# for d in new_tree:
		# 	doc = self.__dict__[d[0]].doc
		# 	print doc.name, doc.lft, doc.rgt
	
	def tearDown(self):
		webnotes.conn.rollback()

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
		update_add_node(d.doctype, d.name, p or '', pf)
	elif op != p:
		update_move_node(d, pf)

	# set old parent
	webnotes.conn.set(d, opf, p or '')

	# reload
	d._loadfromdb()
	
def update_move_node(doc, parent_field):
	# move to dark side
	parent = doc.fields.get(parent_field)
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
	
def update_add_node(doctype, name, parent, parent_field):
	"""
		insert a new node
	"""
	from webnotes.utils import now
	n = now()

	# get the last sibling of the parent
	if parent:
		right = webnotes.conn.sql("select rgt from `tab%s` where name='%s'" % (doctype, parent))[0][0]
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

class DocTypeNestedSet(object):
	def on_update(self):
		update_nsm(self)
		
	def on_trash(self):
		self.doc.fields[self.nsm_parent_field] = ""
		update_nsm(self)
		
	def validate_root_details(self, root, parent_field):
		#does not exists parent
		if self.doc.name==root and self.doc.fields.get(parent_field):
			msgprint("You can not assign parent for root: %s" % (root, ), raise_exception=1)
	
		elif self.doc.name!=root and not self.doc.parent_account:
			msgprint("Parent is mandatory for %s" % (self.doc.name, ), raise_exception=1)
