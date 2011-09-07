import unittest
import urllib, urllib2, os		

class TestREST(unittest.TestCase):		
	def test_home(self):
		req = urllib2.Request('http://localhost/rmehta/wnframework-client/')
		req.get_method = lambda: 'GET'
		response = urllib2.urlopen(req)
		self.assertTrue(response.getcode()==200)

if __name__=='__main__':
	unittest.main()