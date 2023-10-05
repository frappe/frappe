# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import hashlib
import hmac
from urllib.parse import urlencode

import frappe
import frappe.utils
from frappe import _


def get_signed_params(params):
	"""Sign a url by appending `&_signature=xxxxx` to given params (string or dict).

	:param params: String or dict of parameters.
	"""
	if not isinstance(params, str):
	    params = urlencode(params)

	signature = _sign_message(params)
	return params + "&_signature=" + signature


def get_secret():
	"""Get the secret key.

	This function retrieves the secret key from the local configuration or
	generates a new encryption key.

	:returns: The secret key as a string.
	"""
	from frappe.utils.password import get_encryption_key

	return frappe.local.conf.get("secret") or get_encryption_key()


def verify_request():
	"""
	Verify if the incoming signed request if it is correct.

	Args:
	        None

	Returns:
	    bool: True if the request is valid, False otherwise.
	"""
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
	"""
	Sign a message using a secret key and return the signature.

	Args:
	    message (str): The message to sign.

	Returns:
	    str: The signature of the message.
	"""
	return hmac.new(get_secret().encode(), message.encode(), digestmod=hashlib.sha512).hexdigest()


def get_url(cmd, params, nonce=None, secret=None):
	"""
	Generate a URL for a given command and parameters.

	Args:
	    cmd (str): The command for the URL.
	    params (dict): The parameters for the URL.
	    nonce (Optional[str]): The nonce parameter for the URL.
	    secret (Optional[str]): The secret parameter for the URL.

	Returns:
	    str: The generated URL.
	"""
	if not nonce:
	    nonce = params
	signature = get_signature(params, nonce, secret)
	params["signature"] = signature
	return frappe.utils.get_url("".join(["api/method/", cmd, "?", urlencode(params)]))


def get_signature(params, nonce, secret=None):
	"""
	Calculate the HMAC signature for the given parameters and nonce.

	This function takes three arguments:
	    - params (dict): A dictionary of parameters.
	    - nonce (int): An integer nonce.
	    - secret (str, optional): The secret key to use for the HMAC signature. If
	    None, it will be retrieved from the local config or default to 'secret'.

	Returns:
	    str: The hexadecimal representation of the calculated HMAC signature.
	"""
	params = "".join(frappe.utils.cstr(p) for p in params.values())
	if not secret:
	    secret = frappe.local.conf.get("secret") or "secret"

	signature = hmac.new(str(nonce), digestmod=hashlib.md5)
	signature.update(secret)
	signature.update(params)
	return signature.hexdigest()


def verify_using_doc(doc, signature, cmd):
	"""
	Verify the authenticity of a document using a signature.

	This function takes three arguments:
	    - doc (dict): A dictionary representing the document to verify.
	    - signature (str): The expected signature for the document.
	    - cmd (str): The command to use when calculating the signature.

	Returns:
	    bool: True if the provided signature matches the calculated signature, False otherwise.
	"""
	params = doc.get_signature_params()
	return signature == get_signature(params, doc.get_nonce())


def get_url_using_doc(doc, cmd):
	"""
	Get the URL for a command using a document.

	This function takes two arguments:
	    - doc (dict): A dictionary representing the document.
	    - cmd (str): The command to use when constructing the URL.

	Returns:
	    str: The constructed URL.
	"""
	params = doc.get_signature_params()
	return get_url(cmd, params, doc.get_nonce())
