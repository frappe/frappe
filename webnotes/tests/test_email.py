from __future__ import unicode_literals
import os, sys

sys.path.append('.')
sys.path.append('lib/py')
sys.path.append('erpnext')

import unittest, webnotes

class TestEmail(unittest.TestCase):
	def setUp(self):
		webnotes.conn.begin()
		
	def tearDown(self):
		webnotes.conn.rollback()
		
	def test_send(self):
		from webnotes.utils.email_lib import sendmail
		#sendmail('rmehta@gmail.com', subject='Test Mail', msg="Test Content")

	def test_bulk(self):
		from webnotes.utils.email_lib.bulk import send
		send(recipients = ['rmehta@gmail.com', 'rushabh@erpnext.com'], 
			doctype='Lead', email_field='email_id', first_name_field='lead_name',
			last_name_field=None, subject='Testing Bulk', message='This is a bulk mail!')
		
		bulk = webnotes.conn.sql("""select * from `tabBulk Email` where status='Not Sent'""", as_dict=1)
		self.assertEquals(len(bulk), 2)
		self.assertTrue('rmehta@gmail.com' in [d['recipient'] for d in bulk])
		self.assertTrue('rushabh@erpnext.com' in [d['recipient'] for d in bulk])
		self.assertTrue('Unsubscribe' in bulk[0]['message'])

	def test_flush(self):
		self.test_bulk()
		from webnotes.utils.email_lib.bulk import flush
		flush()
		bulk = webnotes.conn.sql("""select * from `tabBulk Email` where status='Sent'""", as_dict=1)
		self.assertEquals(len(bulk), 2)
		self.assertTrue('rmehta@gmail.com' in [d['recipient'] for d in bulk])
		self.assertTrue('rushabh@erpnext.com' in [d['recipient'] for d in bulk])
		webnotes.conn.sql("""delete from `tabBulk Email`""", auto_commit=True)
		
	def test_unsubscribe(self):
		from webnotes.utils.email_lib.bulk import unsubscribe, send
		webnotes.form_dict = {
			'email':'rmehta@gmail.com',
			'type':'Lead',
			'email_field':'email_id'
		}
		unsubscribe()

		send(recipients = ['rmehta@gmail.com', 'rushabh@erpnext.com'], 
			doctype='Lead', email_field='email_id', first_name_field='lead_name',
			last_name_field=None, subject='Testing Bulk', message='This is a bulk mail!')
		
		bulk = webnotes.conn.sql("""select * from `tabBulk Email` where status='Not Sent'""", 
			as_dict=1)
		self.assertEquals(len(bulk), 1)
		self.assertFalse('rmehta@gmail.com' in [d['recipient'] for d in bulk])
		self.assertTrue('rushabh@erpnext.com' in [d['recipient'] for d in bulk])
		self.assertTrue('Unsubscribe' in bulk[0]['message'])
	
	def test_bulk_limit(self):
		from webnotes.utils.email_lib.bulk import unsubscribe, send, BulkLimitCrossedError
		self.assertRaises(BulkLimitCrossedError, send, recipients=['rmehta@gmail.com']*1000, 
				doctype='Lead', email_field='email_id', first_name_field='lead_name',
				last_name_field=None, subject='Testing Bulk', message='This is a bulk mail!')
		
		
if __name__=='__main__':
	webnotes.connect()
	unittest.main()