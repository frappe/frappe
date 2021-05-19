# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import json
import mimetypes
import re

from six import iteritems
from werkzeug.wrappers import Response

import frappe
import frappe.sessions


def build_response(path, data, http_status_code, headers=None):
	# build response
	response = Response()
	response.data = set_content_type(response, data, path)
	response.status_code = http_status_code
	response.headers["X-Page-Name"] = path.encode("ascii", errors="xmlcharrefreplace")
	response.headers["X-From-Cache"] = frappe.local.response.from_cache or False

	add_preload_headers(response)
	if headers:
		for key, val in iteritems(headers):
			response.headers[key] = val.encode("ascii", errors="xmlcharrefreplace")

	return response

def set_content_type(response, data, path):
	if isinstance(data, dict):
		response.mimetype = 'application/json'
		response.charset = 'utf-8'
		data = json.dumps(data)
		return data

	response.mimetype = 'text/html'
	response.charset = 'utf-8'

	# ignore paths ending with .com to avoid unnecessary download
	# https://bugs.python.org/issue22347
	if "." in path and not path.endswith('.com'):
		content_type, encoding = mimetypes.guess_type(path)
		if content_type:
			response.mimetype = content_type
			if encoding:
				response.charset = encoding

	return data

def add_preload_headers(response):
	from bs4 import BeautifulSoup

	try:
		preload = []
		soup = BeautifulSoup(response.data, "lxml")
		for elem in soup.find_all('script', src=re.compile(".*")):
			preload.append(("script", elem.get("src")))

		for elem in soup.find_all('link', rel="stylesheet"):
			preload.append(("style", elem.get("href")))

		links = []
		for _type, link in preload:
			links.append("<{}>; rel=preload; as={}".format(link, _type))

		if links:
			response.headers["Link"] = ",".join(links)
	except Exception:
		import traceback
		traceback.print_exc()

def clear_cache(path=None):
	# TODO: Remove this
	from frappe.website.utils import clear_cache
	return clear_cache(path)
