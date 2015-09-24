import requests
import json
import frappe

class AuthError(Exception):
	pass

class FrappeException(Exception):
	pass

class FrappeClient(object):
	def __init__(self, url, username, password, verify=True):
		self.verify = verify
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
		}, verify=self.verify)

		if r.status_code==200 and r.json().get('message') == "Logged In":
			return r.json()
		else:
			raise AuthError

	def logout(self):
		self.session.get(self.url, params={
			'cmd': 'logout',
		}, verify=self.verify)

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
		res = self.session.get(self.url + "/api/resource/" + doctype, params=params, verify=self.verify)
		return self.post_process(res)

	def insert(self, doc):
		res = self.session.post(self.url + "/api/resource/" + doc.get("doctype"),
			data={"data":frappe.as_json(doc)}, verify=self.verify)
		return self.post_process(res)

	def update(self, doc):
		url = self.url + "/api/resource/" + doc.get("doctype") + "/" + doc.get("name")
		res = self.session.put(url, data={"data":frappe.as_json(doc)}, verify=self.verify)
		return self.post_process(res)

	def bulk_update(self, docs):
		return self.post_request({
			"cmd": "frappe.client.bulk_update",
			"docs": frappe.as_json(docs)
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
			"doclist": frappe.as_json(doclist)
		})

	def get_value(self, doctype, fieldname=None, filters=None):
		return self.get_request({
			"cmd": "frappe.client.get_value",
			"doctype": doctype,
			"fieldname": fieldname or "name",
			"filters": frappe.as_json(filters)
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
			params=params, verify=self.verify)

		return self.post_process(res)

	def rename_doc(self, doctype, old_name, new_name):
		params = {
			"cmd": "frappe.client.rename_doc",
			"doctype": doctype,
			"old_name": old_name,
			"new_name": new_name
		}
		return self.post_request(params)

	def migrate_doctype(self, doctype, filters=None, update=None, verbose=1, exclude=None, preprocess=None):
		"""Migrate records from another doctype"""
		meta = frappe.get_meta(doctype)
		tables = {}
		for df in meta.get_table_fields():
			if verbose: print "getting " + df.options
			tables[df.fieldname] = self.get_list(df.options, limit_page_length=999999)

		# get links
		if verbose: print "getting " + doctype
		docs = self.get_list(doctype, limit_page_length=999999, filters=filters)

		# build - attach children to parents
		if tables:
			docs = [frappe._dict(doc) for doc in docs]
			docs_map = dict((doc.name, doc) for doc in docs)

			for fieldname in tables:
				for child in tables[fieldname]:
					child = frappe._dict(child)
					if child.parent in docs_map:
						docs_map[child.parent].setdefault(fieldname, []).append(child)

		if verbose: print "inserting " + doctype
		for doc in docs:
			if exclude and doc["name"] in exclude:
				continue

			if preprocess:
				preprocess(doc)

			if not doc.get("owner"):
				doc["owner"] = "Administrator"

			if doctype != "User" and not frappe.db.exists("User", doc.get("owner")):
				frappe.get_doc({"doctype": "User", "email": doc.get("owner"),
					"first_name": doc.get("owner").split("@")[0] }).insert()

			if update:
				doc.update(update)

			doc["doctype"] = doctype
			new_doc = frappe.get_doc(doc)
			new_doc.insert()

			if not meta.istable:
				if doctype != "Comment":
					self.migrate_doctype("Comment", {"comment_doctype": doctype, "comment_docname": doc["name"]},
						update={"comment_docname": new_doc.name}, verbose=0)

				if doctype != "File":
					self.migrate_doctype("File", {"attached_to_doctype": doctype,
						"attached_to_name": doc["name"]}, update={"attached_to_name": new_doc.name}, verbose=0)

	def migrate_single(self, doctype):
		doc = self.get_doc(doctype, doctype)
		doc = frappe.get_doc(doc)

		# change modified so that there is no error
		doc.modified = frappe.db.get_single_value(doctype, "modified")
		frappe.get_doc(doc).insert()

	def get_api(self, method, params={}):
		res = self.session.get(self.url + "/api/method/" + method + "/",
			params=params, verify=self.verify)
		return self.post_process(res)

	def post_api(self, method, params={}):
		res = self.session.post(self.url + "/api/method/" + method + "/",
			params=params, verify=self.verify)
		return self.post_process(res)

	def get_request(self, params):
		res = self.session.get(self.url, params=self.preprocess(params), verify=self.verify)
		res = self.post_process(res)
		return res

	def post_request(self, data):
		res = self.session.post(self.url, data=self.preprocess(data), verify=self.verify)
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
