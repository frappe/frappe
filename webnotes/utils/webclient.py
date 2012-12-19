# Simple Web service client for wnframework (ERPNext)
# License MIT
#
# Uses: requests (http://docs.python-requests.org/en/v1.0.0/)
#
# Usage:
# 1. set the server settings, user, password in this file
# 2. user the "insert", "update", "delete" methods to push data
#
# Help:
# Data is sent as JSON objects called "doclist". A doclist is a list of records that represent one transaction (document)
# in ERPNext, both parent (header) and child records.
#
# For what fields to set in the doclist, please check the table columns of the table you want to update

import requests
import unittest
import json

server = "http://localhost/webnotes/erpnext_master/public/server.py"
user = "Administrator"
password = "test"
sid = None
debug = True

class AuthError(Exception): pass

def login(usr=None, pwd=None):
	response = requests.get(server, params = {
		"cmd": "login",
		"usr": usr or user,
		"pwd": pwd or password
	})
	
	if response.json.get("message")=="Logged In":
		global sid
		sid = response.cookies["sid"]
		return response
	else:
		raise AuthError

def insert(doclist):
	if not sid: login()
	response = requests.post(server, params = {
		"cmd": "webnotes.client.insert",
		"doclist": json.dumps(doclist)
	}, cookies = {"sid": sid})
	
	if debug and "exc" in response.json:
		print response.json["exc"]
	
	return response
	
def update(doclist):
	if not sid: login()
	response = requests.post(server, params = {
		"cmd": "webnotes.client.save",
		"doclist": json.dumps(doclist)
	}, cookies = {"sid": sid})
	
	if debug and "exc" in response.json:
		print response.json["exc"]
	
	return response
	
def delete(doctype, name):
	if not sid: login()
	response = requests.post(server, params = {
		"cmd": "webnotes.model.delete_doc",
		"doctype": doctype,
		"name": name
	}, cookies = {"sid": sid})

	if debug and "exc" in response.json:
		print response.json["exc"]

	return response

class TestAPI(unittest.TestCase):
	def test_login(self):
		global sid
		response = login()
		self.assertTrue(response.json.get("message")=="Logged In")
		self.assertTrue(sid)		
		self.assertRaises(AuthError, login, {"pwd":"--"})
		sid = None
		
	def test_insert(self):
		login()
		response = insert([{
			"doctype":"Customer",
			"customer_name": "Import Test Customer",
			"customer_type": "Company",
			"customer_group": "Standard Group",
			"territory": "Default",
			"company": "Alpha"
		}])
		self.assertTrue(response.json["message"][0]["name"]=="Import Test Customer")
		self.assertTrue(delete("Customer", "Import Test Customer").json["message"]=="okay")
		
if __name__=="__main__":
	unittest.main()