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

def verify_using_bean(bean, signature, cmd):
	controller = bean.get_controller()
	params = controller.get_signature_params()
	params["cmd"] = cmd
	return signature == get_signature(params, controller.get_nonce())
	
def get_url_using_bean(bean, cmd):
	controller = bean.get_controller()
	params = controller.get_signature_params()
	params["cmd"] = cmd
	return get_url(params, controller.get_nonce())