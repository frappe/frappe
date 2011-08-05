"""
	Tests for handler
	
	Note: Please set your local path to run this test
"""

from webnotes.run_tests import TestCase
import webnotes

from webnotes.utils.webservice import FrameworkServer

test_record = {
	'name': 'SB000x',
	'test_data': 'value',
	'test_date': '2011-01-22',
	'test_select': 'A'
}

class TestHandler(TestCase):
	def setUp(self):

		# set your path here
		self.server = FrameworkServer('localhost','wnframework','Administrator', 'admin')
				
	def test_login(self):
		self.assertTrue(self.server.sid is not None)
	
	def test_insert(self):
		resp = self.server.get_response('POST', 'core/sandbox', test_record)
		self.assertTrue(resp['message'] == 'ok')

		resp = self.server.get_response('DELETE', 'core/sandbox/SB000x', test_record)
		
	def test_read(self):
		resp = self.server.get_response('POST', 'core/sandbox', test_record)
		self.assertTrue(resp['message'] == 'ok')

		resp = self.server.get_response('GET', 'core/sandbox/SB000x')
		self.assertTrue(resp['SB000x']['test_data']=='value')

		resp = self.server.get_response('DELETE', 'core/sandbox/SB000x', test_record)
	