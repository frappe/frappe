# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import hmac
import urllib

import frappe
import frappe.utils

def get_url(cmd, params, nonce, secret=None):
	signature = get_signature(params, nonce, secret)
	params['signature'] = signature
	return frappe.utils.get_url("".join(['api/method/', cmd, '?', urllib.urlencode(params)]))
	
def get_signature(params, nonce, secret=None):
	params = "".join((frappe.utils.cstr(p) for p in params.values()))
	if not secret:
		secret = frappe.local.conf.get("secret") or "secret"
		
	signature = hmac.new(str(nonce))
	signature.update(secret)
	signature.update(params)
	return signature.hexdigest()

def verify_using_doc(doc, signature, cmd):
	params = doc.get_signature_params()
	return signature == get_signature(params, doc.get_nonce())
	
def get_url_using_doc(doc, cmd):
	params = doc.get_signature_params()
	return get_url(cmd, params, doc.get_nonce())
