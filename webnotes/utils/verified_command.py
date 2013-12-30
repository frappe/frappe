# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import hmac
import urllib

import webnotes
from webnotes.utils import cstr

def get_url(params, nonce, secret=None):
	signature = get_signature(params, nonce, secret)
	params['signature'] = signature
	return ''.join([webnotes.local.request.url_root, '?', urllib.urlencode(params)])
	
def get_signature(params, nonce, secret=None):
	params = "".join((cstr(p) for p in params))
	if not secret:
		secret = webnotes.local.conf.get("secret") or "secret"
		
	signature = hmac.new(nonce)
	signature.update(secret)
	signature.update(params)
	return signature.hexdigest()

def verify_using_bean(bean, signature):
	controller = bean.get_controller()
	return signature == get_signature(controller.get_signature_params(), controller.get_nonce())
	
def get_url_using_bean(bean):
	controller = bean.get_controller()
	return get_url(controller.get_signature_params(), controller.get_nonce())