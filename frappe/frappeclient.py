import requests
import json
import frappe

class AuthError(Exception):
	pass

class FrappeException(Exception):
	pass

class FrappeClient(object):
	def __init__(self, url, username, password):
		self.session = requests.session()
		self.url = url
		self.login(username, password)

	def __enter__(self):
		return self

	def __exit__(self, *args, **kwargs):
		self.logout()

	def login(self, username, password):
		r = self.session.post(self.url, data={
			'cmd': 'login',
			'usr': username,
			'pwd': password
		})

		if r.json().get('message') == "Logged In":
			return r.json()
		else:
			raise AuthError

	def logout(self):
		self.session.get(self.url, params={
			'cmd': 'logout',
		})

	def get_list(self, doctype, fields='"*"', filters=None, limit_start=0, limit_page_length=0):
		"""Returns list of records of a particular type"""
		if not isinstance(fields, basestring):
			fields = json.dumps(fields)
		params = {
			"fields": fields,
		}
		if filters:
			params["filters"] = json.dumps(filters)
		if limit_page_length:
			params["limit_start"] = limit_start
			params["limit_page_length"] = limit_page_length
		print self.url
		res = self.session.get(self.url + "/api/resource/" + doctype, params=params)
		return self.post_process(res)

	def insert(self, doc):
		res = self.session.post(self.url + "/api/resource/" + doc.get("doctype"),
			data={"data":json.dumps(doc)})
		return self.post_process(res)

	def update(self, doc):
		url = self.url + "/api/resource/" + doc.get("doctype") + "/" + doc.get("name")
		res = self.session.put(url, data={"data":json.dumps(doc)})
		return self.post_process(res)

	def bulk_update(self, docs):
		return self.post_request({
			"cmd": "frappe.client.bulk_update",
			"docs": json.dumps(docs)
		})

	def delete(self, doctype, name):
		return self.post_request({
			"cmd": "frappe.model.delete_doc",
			"doctype": doctype,
			"name": name
		})

	def submit(self, doclist):
		return self.post_request({
			"cmd": "frappe.client.submit",
			"doclist": json.dumps(doclist)
		})

	def get_value(self, doctype, fieldname=None, filters=None):
		return self.get_request({
			"cmd": "frappe.client.get_value",
			"doctype": doctype,
			"fieldname": fieldname or "name",
			"filters": json.dumps(filters)
		})

	def set_value(self, doctype, docname, fieldname, value):
		return self.post_request({
			"cmd": "frappe.client.set_value",
			"doctype": doctype,
			"name": docname,
			"fieldname": fieldname,
			"value": value
		})

	def cancel(self, doctype, name):
		return self.post_request({
			"cmd": "frappe.client.cancel",
			"doctype": doctype,
			"name": name
		})

	def get_doc(self, doctype, name="", filters=None, fields=None):
		params = {}
		if filters:
			params["filters"] = json.dumps(filters)
                if fields:
                        params["fields"] = json.dumps(fields)

		res = self.session.get(self.url + "/api/resource/" + doctype + "/" + name,
			params=params)

		return self.post_process(res)

	def rename_doc(self, doctype, old_name, new_name):
		params = {
			"cmd": "frappe.client.rename_doc",
			"doctype": doctype,
			"old_name": old_name,
			"new_name": new_name
		}
		return self.post_request(params)

	def migrate_doctype(self, doctype, filters={}):
		"""Migrate records from another doctype"""
		meta = frappe.get_meta(doctype)
		tables = {}
		for df in meta.get_table_fields():
			print "getting " + df.options
			tables[df.fieldname] = self.get_list(df.options, limit_page_length=999999)

		# get links
		print "getting " + doctype
		docs = self.get_list(doctype, limit_page_length=999999, filters=filters)

		# build - attach children to parents
		if tables:
			docs_map = {}
			for doc in docs:
				docs_map[doc.name] = doc

			for fieldname in tables:
				for child in tables[fieldname]:
					docs_map[child.parent].append(fieldname, child)

		print "inserting " + doctype
		for doc in docs:
			if not frappe.db.exists("User", doc.get("owner")):
				frappe.get_doc({"doctype": "User", "email": doc.get("owner"),
					"first_name": doc.get("owner").split("@")[0] }).insert()

			doc["doctype"] = doctype
			frappe.get_doc(doc).insert()

		if doctype != "Comment":
			self.migrate_doctype("Comment", {"comment_doctype": doctype})

	def migrate_single(self, doctype):
		doc = self.get_doc(doctype, doctype)
		doc = frappe.get_doc(doc)

		# change modified so that there is no error
		doc.modified = frappe.db.get_single_value(doctype, "modified")
		frappe.get_doc(doc).insert()

	def get_api(self, method, params={}):
		res = self.session.get(self.url + "/api/method/" + method + "/",
			params=params)
		return self.post_process(res)

	def post_api(self, method, params={}):
		res = self.session.post(self.url + "/api/method/" + method + "/",
			params=params)
		return self.post_process(res)

	def get_request(self, params):
		res = self.session.get(self.url, params=self.preprocess(params))
		res = self.post_process(res)
		return res

	def post_request(self, data):
		res = self.session.post(self.url, data=self.preprocess(data))
		res = self.post_process(res)
		return res

	def preprocess(self, params):
		"""convert dicts, lists to json"""
		for key, value in params.iteritems():
			if isinstance(value, (dict, list)):
				params[key] = json.dumps(value)

		return params

	def post_process(self, response):
		try:
			rjson = response.json()
		except ValueError:
			print response.text
			raise

		if rjson and ("exc" in rjson) and rjson["exc"]:
			raise FrappeException(rjson["exc"])
		if 'message' in rjson:
			return rjson['message']
		elif 'data' in rjson:
			return rjson['data']
		else:
			return None
