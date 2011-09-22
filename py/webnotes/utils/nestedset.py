# Tree (Hierarchical) Nested Set Model (nsm)
# 
# To use the nested set model,
# use the following pattern
# 1. name your parent field as "parent_node" if not have a property nsm_parent_field as your field name in the document class
# 2. have a field called "old_parent" in your fields list - this identifies whether the parent has been changed
# 3. call update_nsm(doc_obj) in the on_upate method

# ------------------------------------------

import webnotes, unittest

class TestNSM(unittest.TestCase):
	
	def setUp(self):
		from webnotes.model.doc import Document
		self.root = Document(fielddata={'doctype':'nsmtest', 'name':'T001', 'parent':None})
		self.first_child = Document(fielddata={'doctype':'nsmtest', 'name':'C001', 'parent_node':'T001'})
		self.first_sibling = Document(fielddata={'doctype':'nsmtest', 'name':'C002', 'parent_node':'T001'})
		self.grand_child = Document(fielddata={'doctype':'nsmtest', 'name':'GC001', 'parent_node':'C001'}) 

		webnotes.conn.sql("""
			create table `tabnsmtest` (
				name varchar(120) not null primary key, 
				creation datetime,
				modified datetime,
				modified_by varchar(40), 
				owner varchar(40),
				docstatus int(1) default '0', 
				parent varchar(120),
				parentfield varchar(120), 
				parenttype varchar(120), 
				idx int(8),
				parent_node varchar(180), 
				old_parent varchar(180), 
				lft int, 
				rgt int) ENGINE=InnoDB""")
		
	def test_root(self):
		self.root.save(1)
		update_nsm(self.root)
		self.assertTrue(self.root.lft==1)
		self.assertTrue(self.root.rgt==2)
	
	def test_first_child(self):
		self.root.save(1)
		update_nsm(self.root)

		self.first_child.save(1)
		update_nsm(self.first_child)

		self.root._loadfromdb()
		
		self.assertTrue(self.root.lft==1)
		self.assertTrue(self.first_child.lft==2)
		self.assertTrue(self.first_child.rgt==3)
		self.assertTrue(self.root.rgt==4)
		
	def test_sibling(self):
		self.test_first_child()
		
		self.first_sibling.save(1)
		update_nsm(self.first_sibling)
		
		self.root._loadfromdb()
		self.first_child._loadfromdb()
		
		self.assertTrue(self.root.lft==1)
		self.assertTrue(self.first_child.lft==2)
		self.assertTrue(self.first_child.rgt==3)
		self.assertTrue(self.first_sibling.lft==4)
		self.assertTrue(self.first_sibling.rgt==5)
		self.assertTrue(self.root.rgt==6)
		
	def test_remove_sibling(self):
		self.test_sibling()
		self.first_sibling.parent_node = ''
		update_nsm(self.first_sibling)

		self.root._loadfromdb()
		self.first_child._loadfromdb()

		self.assertTrue(self.root.lft==1)
		self.assertTrue(self.first_child.lft==2)
		self.assertTrue(self.first_child.rgt==3)
		self.assertTrue(self.root.rgt==4)
		self.assertTrue(self.first_sibling.lft==5)
		self.assertTrue(self.first_sibling.rgt==6)
		
	def test_change_parent(self):
		self.test_sibling()
		
		# add grand child
		self.grand_child.save(1)
		update_nsm(self.grand_child)
		
		# check lft rgt
		self.assertTrue(self.grand_child.lft==3)
		self.assertTrue(self.grand_child.rgt==4)

		# change parent
		self.grand_child.parent_node = 'C002'
		self.grand_child.save()
		
		# update
		update_nsm(self.grand_child)

		# check lft rgt
		self.assertTrue(self.grand_child.lft==5)
		self.assertTrue(self.grand_child.rgt==6)
		

	def tearDown(self):
		webnotes.conn.sql("drop table tabnsmtest")



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
		update_remove_node(d.doctype, d.name)
		update_add_node(d.doctype, d.name, p or '', pf)
		
	# set old parent
	webnotes.conn.set(d, opf, p or '')

	# reload
	d._loadfromdb()
	
def rebuild_tree(doctype, parent_field):
	"""
		call rebuild_node for all root nodes
	"""
	# get all roots
	right = 1
	result = webnotes.conn.sql("SELECT name FROM `tab%s` WHERE `%s`='' or `%s` IS NULL ORDER BY name ASC" % (doctype, parent_field, parent_field))
	for r in result:
		right = rebuild_node(doctype, r[0], right, parent_field)
		
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

def update_remove_node(doctype, name):
	"""
		remove a node
	"""
	from webnotes.utils import now
	n = now()

	left = webnotes.conn.sql("select lft from `tab%s` where name='%s'" % (doctype,name))
	if left[0][0]:
		# reset this node
		webnotes.conn.sql("update `tab%s` set lft=0, rgt=0, modified='%s' where name='%s'" % (doctype,n,name))

		# update all on the right
		webnotes.conn.sql("update `tab%s` set rgt = rgt-2, modified='%s' where rgt > %s" %(doctype,n,left[0][0]))
		webnotes.conn.sql("update `tab%s` set lft = lft-2, modified='%s' where lft > %s" %(doctype,n,left[0][0]))

