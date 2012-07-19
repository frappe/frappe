from __future__ import unicode_literals
import unittest, sys

sys.path.append('lib/py')

import webnotes
from webnotes.model import docfield
webnotes.connect()

class TestDocField(unittest.TestCase):
	def test_rename(self):
		docfield.rename('Event', 'notes', 'notes1')
		
		# check in table
		tf = webnotes.conn.sql("""desc tabEvent""")
		
		self.assertTrue('notes' not in [d[0] for d in tf])
		self.assertTrue('notes1' in [d[0] for d in tf])

		docfield.rename('Event', 'notes1', 'notes')
	
	def test_table_rename(self):
		docfield.rename('Event', 'event_individuals', 'event_users')

		self.assertFalse(webnotes.conn.sql("""select parent from `tabEvent User` where parentfield='event_individuals'"""))
		self.assertTrue(webnotes.conn.sql("""select parent from `tabEvent User` where parentfield='event_users'"""))

		
if __name__=='__main__':
	unittest.main()