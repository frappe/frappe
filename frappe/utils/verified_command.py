# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import hashlib
import hmac

from six import string_types
from six.moves.urllib.parse import urlencode

import frappe
import frappe.utils
from frappe import _


def get_signed_params(params):
	"""Sign a url by appending `&_signature=xxxxx` to given params (string or dict).

	:param params: String or dict of parameters."""
	if not isinstance(params, string_types):
		params = urlencode(params)

	signature = _sign_message(params)
	return params + "&_signature=" + signature


def get_secret():
	from frappe.utils.password import get_encryption_key

	return frappe.local.conf.get("secret") or get_encryption_key()


def verify_request():
	"""Verify if the incoming signed request if it is correct."""
	query_string = frappe.safe_decode(
		frappe.local.flags.signed_query_string or getattr(frappe.request, "query_string", None)
	)

	signature_string = "&_signature="
	if signature_string in query_string:
		params, given_signature = query_string.split(signature_string)

		computed_signature = _sign_message(params)
		valid_signature = hmac.compare_digest(given_signature, computed_signature)
		valid_method = frappe.request.method == "GET"
		valid_request_data = not (frappe.request.form or frappe.request.data)

		if valid_signature and valid_method and valid_request_data:
			return True

	frappe.respond_as_web_page(
		_("Invalid Link"),
		_("This link is invalid or expired. Please make sure you have pasted correctly."),
	)

	return False


def _sign_message(message: str) -> str:
	return hmac.new(get_secret().encode(), message.encode(), digestmod=hashlib.sha512).hexdigest()


def get_url(cmd, params, nonce=None, secret=None):
	if not nonce:
		nonce = params
	signature = get_signature(params, nonce, secret)
	params["signature"] = signature
	return frappe.utils.get_url("".join(["api/method/", cmd, "?", urlencode(params)]))


def get_signature(params, nonce, secret=None):
	params = "".join((frappe.utils.cstr(p) for p in params.values()))
	if not secret:
		secret = frappe.local.conf.get("secret") or "secret"

	signature = hmac.new(str(nonce), digestmod=hashlib.md5)
	signature.update(secret)
	signature.update(params)
	return signature.hexdigest()


def verify_using_doc(doc, signature, cmd):
	params = doc.get_signature_params()
	return signature == get_signature(params, doc.get_nonce())


def get_url_using_doc(doc, cmd):
	params = doc.get_signature_params()
	return get_url(cmd, params, doc.get_nonce())
