# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

# Simple Web service client for wnframework (ERPNext)
# License MIT
#
# Uses: requests (http://docs.python-requests.org/en/v1.0.0/)
#
# Usage:
# 1. set the server settings, user, password in this file
# 2. use the "insert", "update", "delete" methods to push data
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
	return post_request({
		"cmd": "webnotes.client.insert",
		"doclist": json.dumps(doclist)
	})
	
def update(doclist):
	return post_request({
		"cmd": "webnotes.client.save",
		"doclist": json.dumps(doclist)
	})

def delete(doctype, name):
	return post_request({
		"cmd": "webnotes.model.delete_doc",
		"doctype": doctype,
		"name": name
	})
	
def submit(doclist):
	return post_request({
		"cmd": "webnotes.client.submit",
		"doclist": json.dumps(doclist)
	})


def cancel(doctype, name):
	return post_request({
		"cmd": "webnotes.client.cancel",
		"doctype": doctype,
		"name": name
	})
	
def get_doc(doctype, name=None, filters=None):
	params = {
		"cmd": "webnotes.client.get",
		"doctype": doctype,
	}
	if name:
		params["name"] = name
	if filters:
		params["filters"] = json.dumps(filters)
	ret = get_request(params)
	return ret

def get_request(params):
	if not sid: login()
	response = requests.get(server, params = params, cookies = {"sid": sid})
	return post_process(response)

def post_request(params):
	if not sid: login()
	response = requests.post(server, data = params, cookies = {"sid": sid})
	return post_process(response)
	
def post_process(response):
	if debug and response.json and ("exc" in response.json) and response.json["exc"]:
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
		
	def test_all(self):
		login()
		delete("Customer", "Import Test Customer")
		response = insert([{
			"doctype":"Customer",
			"customer_name": "Import Test Customer",
			"customer_type": "Company",
			"customer_group": "Standard Group",
			"territory": "Default",
			"customer_details": "some unique info",
			"company": "Alpha"
		}])
		self.assertTrue(response.json["message"][0]["name"]=="Import Test Customer")
		
		# get
		response = get_doc("Customer", "Import Test Customer")
		self.check_get(response)
		
		response = get_doc("Customer", filters={"customer_details":"some unique info"})
		self.check_get(response)
		
		# delete
		self.assertTrue(delete("Customer", "Import Test Customer").json["message"]=="okay")
	
	def check_get(self, response):
		doclist = response.json["message"]
		self.assertTrue(len(doclist)==1)
		self.assertTrue(doclist[0]["doctype"]=="Customer")
		self.assertTrue(doclist[0]["customer_group"]=="Standard Group")
	
if __name__=="__main__":
	unittest.main()
