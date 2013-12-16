import unittest, webnotes

# TODO - rewrite this in Item Group

# class TestNSM(unittest.TestCase):
# 	def setUp(self):
# 		webnotes.conn.sql("""delete from `tabItem Group` 
# 			where (name like 'c%') or (name like 'gc%')""")
# 			
# 						
# 		self.data = [
# 			["All Item Groups", None, 1, 20], 
# 				["c0", "All Item Groups", 2, 3],
# 				["c1", "All Item Groups", 4, 11],
# 					["gc1", "c1", 5, 6],
# 					["gc2", "c1", 7, 8],
# 					["gc3", "c1", 9, 10],
# 				["c2", "All Item Groups", 12, 17],
# 					["gc4", "c2", 13, 14],
# 					["gc5", "c2", 15, 16],
# 				["c3", "All Item Groups", 18, 19]
# 		]
# 		
# 		for d in self.data:
# 			b = webnotes.bean([{
# 				"doctype": "Item Group", "item_group_name": d[0], "parent_item_group": d[1],
# 				"__islocal": 1, "is_group": "Yes"
# 			}])
# 			b.insert()
# 			self.__dict__[d[0]] = b
# 			
# 			
# 		self.reload_all()
# 
# 	def reload_all(self, data=None):
# 		for d in data or self.data:
# 			self.__dict__[d[0]].load_from_db()
# 			
# 	def test_basic_tree(self, data=None):
# 		for d in data or self.data:
# 			self.assertEquals(self.__dict__[d[0]].doc.lft, d[2])
# 			self.assertEquals(self.__dict__[d[0]].doc.rgt, d[3])
# 	
# 	def test_validate_loop_move(self):
# 		self.c1.doc.parent_item_group = 'gc3'
# 		self.assertRaises(webnotes.ValidationError, self.c1.save)
# 	
# 	def test_rebuild_tree(self):
# 		from webnotes.utils.nestedset import rebuild_tree
# 		rebuild_tree("Item Group", "parent_item_group")
# 		self.test_basic_tree(self.data)
# 	
# 	def test_move_group(self):
# 		self.c1.doc.parent_item_group = 'c2'
# 		self.c1.save()
# 		self.reload_all()
# 		
# 		new_tree = [
# 			["All Item Groups", None, 1, 20], 
# 				["c0", "All Item Groups", 2, 3],
# 				["c2", "All Item Groups", 4, 17],
# 					["gc4", "c2", 5, 6],
# 					["gc5", "c2", 7, 8],
# 					["c1", "All Item Groups", 9, 16],
# 						["gc1", "c1", 10, 11],
# 						["gc2", "c1", 12, 13],
# 						["gc3", "c1", 14, 15],
# 				["c3", "All Item Groups", 18, 19]
# 		]
# 		self.test_basic_tree(new_tree)
# 		
# 		# Move back
# 		
# 		self.c1.doc.parent_item_group = 'gc4'
# 		self.c1.save()
# 		self.reload_all()
# 		
# 		new_tree = [
# 			["All Item Groups", None, 1, 20], 
# 				["c0", "All Item Groups", 2, 3],
# 				["c2", "All Item Groups", 4, 17],
# 					["gc4", "c2", 5, 14],
# 						["c1", "All Item Groups", 6, 13],
# 							["gc1", "c1", 7, 8],
# 							["gc2", "c1", 9, 10],
# 							["gc3", "c1", 11, 12],
# 					["gc5", "c2", 15, 16],
# 				["c3", "All Item Groups", 18, 19]
# 		]
# 		self.test_basic_tree(new_tree)
# 
# 		# Move to root
# 		
# 		# self.c1.doc.parent_item_group = ''
# 		# self.c1.save()
# 		# self.reload_all()
# 		# 
# 		# new_tree = [
# 		# 	["All Item Groups", None, 1, 12],
# 		# 		["c0", "All Item Groups", 2, 3],
# 		# 		["c2", "All Item Groups", 4, 9],
# 		# 			["gc4", "c2", 5, 6],
# 		# 			["gc5", "c2", 7, 8],
# 		# 		["c3", "All Item Groups", 10, 11],
# 		# 	["c1", "All Item Groups", 13, 20],
# 		# 		["gc1", "c1", 14, 15],
# 		# 		["gc2", "c1", 16, 17],
# 		# 		["gc3", "c1", 18, 19],
# 		# ]
# 		# self.test_basic_tree(new_tree)
# 		
# 		# move leaf
# 		self.gc3.doc.parent_item_group = 'c2'
# 		self.gc3.save()
# 		self.reload_all()
# 		
# 		new_tree = [
# 			["All Item Groups", None, 1, 20], 
# 				["c0", "All Item Groups", 2, 3],
# 				["c2", "All Item Groups", 4, 17],
# 					["gc4", "c2", 5, 12],
# 						["c1", "All Item Groups", 6, 11],
# 							["gc1", "c1", 7, 8],
# 							["gc2", "c1", 9, 10],
# 					["gc5", "c2", 13, 14],
# 					["gc3", "c2", 15, 16],
# 				["c3", "All Item Groups", 18, 19]
# 		]
# 		self.test_basic_tree(new_tree)
# 		
# 		# delete leaf
# 		from webnotes.model import delete_doc
# 		delete_doc(self.gc2.doc.doctype, self.gc2.doc.name)
# 		
# 		new_tree = [
# 			["All Item Groups", None, 1, 18], 
# 				["c0", "All Item Groups", 2, 3],
# 				["c2", "All Item Groups", 4, 15],
# 					["gc4", "c2", 5, 10],
# 						["c1", "All Item Groups", 6, 9],
# 							["gc1", "c1", 7, 8],
# 					["gc5", "c2", 11, 12],
# 					["gc3", "c2", 13, 14],
# 				["c3", "All Item Groups", 16, 17]
# 		]
# 		
# 		del self.__dict__["gc2"]
# 		self.reload_all(new_tree)
# 		self.test_basic_tree(new_tree)
# 			
# if __name__=="__main__":
# 	import webnotes
# 	webnotes.connect()
# 	unittest.main()