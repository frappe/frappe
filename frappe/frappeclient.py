from __future__ import print_function, unicode_literals
import requests
import json
import frappe
from six import iteritems, string_types
import base64

'''
FrappeClient is a library that helps you connect with other frappe systems
'''

class AuthError(Exception):
	pass

class SiteExpiredError(Exception):
	pass

class SiteUnreachableError(Exception):
	pass

class FrappeException(Exception):
	pass

class FrappeClient(object):
	def __init__(self, url, username=None, password=None, verify=True, api_key=None, api_secret=None, frappe_authorization_source=None):
		self.headers = {
			'Accept': 'application/json',
			'content-type': 'application/x-www-form-urlencoded',
		}
		self.verify = verify
		self.session = requests.session()
		self.url = url
		self.api_key = api_key
		self.api_secret = api_secret
		self.frappe_authorization_source = frappe_authorization_source

		self.setup_key_authentication_headers()

		# login if username/password provided
		if username and password:
			self._login(username, password)

	def __enter__(self):
		return self

	def __exit__(self, *args, **kwargs):
		self.logout()

	def _login(self, username, password):
		'''Login/start a sesion. Called internally on init'''
		r = self.session.post(self.url, data={
			'cmd': 'login',
			'usr': username,
			'pwd': password
		}, verify=self.verify, headers=self.headers)

		if r.status_code==200 and r.json().get('message') in ("Logged In", "No App"):
			return r.json()
		elif r.status_code == 502:
			raise SiteUnreachableError
		else:
			try:
				error = json.loads(r.text)
				if error.get('exc_type') == "SiteExpiredError":
					raise SiteExpiredError
			except json.decoder.JSONDecodeError:
				error = r.text
				print(error)
			raise AuthError

	def setup_key_authentication_headers(self):
		if self.api_key and self.api_secret:
			token = base64.b64encode(('{}:{}'.format(self.api_key, self.api_secret)).encode('utf-8')).decode('utf-8')
			auth_header = {
				'Authorization': 'Basic {}'.format(token),
			}
			self.headers.update(auth_header)

			if self.frappe_authorization_source:
				auth_source = {'Frappe-Authorization-Source': self.frappe_authorization_source}
				self.headers.update(auth_source)

	def logout(self):
		'''Logout session'''
		self.session.get(self.url, params={
			'cmd': 'logout',
		}, verify=self.verify, headers=self.headers)

	def get_list(self, doctype, fields='["name"]', filters=None, limit_start=0, limit_page_length=0):
		"""Returns list of records of a particular type"""
		if not isinstance(fields, string_types):
			fields = json.dumps(fields)
		params = {
			"fields": fields,
		}
		if filters:
			params["filters"] = json.dumps(filters)
		if limit_page_length:
			params["limit_start"] = limit_start
			params["limit_page_length"] = limit_page_length
		res = self.session.get(self.url + "/api/resource/" + doctype, params=params, verify=self.verify, headers=self.headers)
		return self.post_process(res)

	def insert(self, doc):
		'''Insert a document to the remote server

		:param doc: A dict or Document object to be inserted remotely'''
		res = self.session.post(self.url + "/api/resource/" + doc.get("doctype"),
			data={"data":frappe.as_json(doc)}, verify=self.verify, headers=self.headers)
		return frappe._dict(self.post_process(res))

	def insert_many(self, docs):
		'''Insert multiple documents to the remote server

		:param docs: List of dict or Document objects to be inserted in one request'''
		return self.post_request({
			"cmd": "frappe.client.insert_many",
			"docs": frappe.as_json(docs)
		})

	def update(self, doc):
		'''Update a remote document

		:param doc: dict or Document object to be updated remotely. `name` is mandatory for this'''
		url = self.url + "/api/resource/" + doc.get("doctype") + "/" + doc.get("name")
		res = self.session.put(url, data={"data":frappe.as_json(doc)}, verify=self.verify, headers=self.headers)
		return frappe._dict(self.post_process(res))

	def bulk_update(self, docs):
		'''Bulk update documents remotely

		:param docs: List of dict or Document objects to be updated remotely (by `name`)'''
		return self.post_request({
			"cmd": "frappe.client.bulk_update",
			"docs": frappe.as_json(docs)
		})

	def delete(self, doctype, name):
		'''Delete remote document by name

		:param doctype: `doctype` to be deleted
		:param name: `name` of document to be deleted'''
		return self.post_request({
			"cmd": "frappe.client.delete",
			"doctype": doctype,
			"name": name
		})

	def submit(self, doc):
		'''Submit remote document

		:param doc: dict or Document object to be submitted remotely'''
		return self.post_request({
			"cmd": "frappe.client.submit",
			"doc": frappe.as_json(doc)
		})

	def get_value(self, doctype, fieldname=None, filters=None):
		'''Returns a value form a document

		:param doctype: DocType to be queried
		:param fieldname: Field to be returned (default `name`)
		:param filters: dict or string for identifying the record'''
		return self.get_request({
			"cmd": "frappe.client.get_value",
			"doctype": doctype,
			"fieldname": fieldname or "name",
			"filters": frappe.as_json(filters)
		})

	def set_value(self, doctype, docname, fieldname, value):
		'''Set a value in a remote document

		:param doctype: DocType of the document to be updated
		:param docname: name of the document to be updated
		:param fieldname: fieldname of the document to be updated
		:param value: value to be updated'''
		return self.post_request({
			"cmd": "frappe.client.set_value",
			"doctype": doctype,
			"name": docname,
			"fieldname": fieldname,
			"value": value
		})

	def cancel(self, doctype, name):
		'''Cancel a remote document

		:param doctype: DocType of the document to be cancelled
		:param name: name of the document to be cancelled'''
		return self.post_request({
			"cmd": "frappe.client.cancel",
			"doctype": doctype,
			"name": name
		})

	def get_doc(self, doctype, name="", filters=None, fields=None):
		'''Returns a single remote document

		:param doctype: DocType of the document to be returned
		:param name: (optional) `name` of the document to be returned
		:param filters: (optional) Filter by this dict if name is not set
		:param fields: (optional) Fields to be returned, will return everythign if not set'''
		params = {}
		if filters:
			params["filters"] = json.dumps(filters)
		if fields:
			params["fields"] = json.dumps(fields)

		res = self.session.get(self.url + "/api/resource/" + doctype + "/" + name,
			params=params, verify=self.verify, headers=self.headers)

		return self.post_process(res)

	def rename_doc(self, doctype, old_name, new_name):
		'''Rename remote document

		:param doctype: DocType of the document to be renamed
		:param old_name: Current `name` of the document to be renamed
		:param new_name: New `name` to be set'''
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
			if verbose: print("getting " + df.options)
			tables[df.fieldname] = self.get_list(df.options, limit_page_length=999999)

		# get links
		if verbose: print("getting " + doctype)
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

		if verbose: print("inserting " + doctype)
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
				if doctype != "Communication":
					self.migrate_doctype("Communication", {"reference_doctype": doctype, "reference_name": doc["name"]},
						update={"reference_name": new_doc.name}, verbose=0)

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
			params=params, verify=self.verify, headers=self.headers)
		return self.post_process(res)

	def post_api(self, method, params={}):
		res = self.session.post(self.url + "/api/method/" + method + "/",
			params=params, verify=self.verify, headers=self.headers)
		return self.post_process(res)

	def get_request(self, params):
		res = self.session.get(self.url, params=self.preprocess(params), verify=self.verify, headers=self.headers)
		res = self.post_process(res)
		return res

	def post_request(self, data):
		res = self.session.post(self.url, data=self.preprocess(data), verify=self.verify, headers=self.headers)
		res = self.post_process(res)
		return res

	def preprocess(self, params):
		"""convert dicts, lists to json"""
		for key, value in iteritems(params):
			if isinstance(value, (dict, list)):
				params[key] = json.dumps(value)

		return params

	def post_process(self, response):
		try:
			rjson = response.json()
		except ValueError:
			print(response.text)
			raise

		if rjson and ("exc" in rjson) and rjson["exc"]:
			try:
				exc = json.loads(rjson["exc"])[0]
				exc = 'FrappeClient Request Failed\n\n' + exc
			except Exception:
				exc = rjson["exc"]

			raise FrappeException(exc)
		if 'message' in rjson:
			return rjson['message']
		elif 'data' in rjson:
			return rjson['data']
		else:
			return None

class FrappeOAuth2Client(FrappeClient):
	def __init__(self, url, access_token, verify=True):
		self.access_token = access_token
		self.headers = {
			"Authorization": "Bearer " + access_token,
			"content-type": "application/x-www-form-urlencoded"
		}
		self.verify = verify
		self.session = OAuth2Session(self.headers)
		self.url = url

	def get_request(self, params):
		res = requests.get(self.url, params=self.preprocess(params), headers=self.headers, verify=self.verify)
		res = self.post_process(res)
		return res

	def post_request(self, data):
		res = requests.post(self.url, data=self.preprocess(data), headers=self.headers, verify=self.verify)
		res = self.post_process(res)
		return res

class OAuth2Session():
	def __init__(self, headers):
		self.headers = headers
	def get(self, url, params, verify):
		res = requests.get(url, params=params, headers=self.headers, verify=verify)
		return res
	def post(self, url, data, verify):
		res = requests.post(url, data=data, headers=self.headers, verify=verify)
		return res
	def put(self, url, data, verify):
		res = requests.put(url, data=data, headers=self.headers, verify=verify)
		return res
