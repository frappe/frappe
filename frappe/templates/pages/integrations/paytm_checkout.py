# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint
import json
from six import string_types
from frappe.utils import get_request_site_address
from frappe.integrations.doctype.paytm_settings.paytm_settings import get_paytm_params, get_paytm_config
import requests

no_cache = 1

def get_context(context):
	context.no_cache = 1
	paytm_config = get_paytm_config()

	try:
		doc = frappe.get_doc("Integration Request", frappe.form_dict['order_id'])

		context.payment_details = get_paytm_params(json.loads(doc.data), doc.name, paytm_config)

		context.url = paytm_config.url

	except Exception as e:
		frappe.log_error()
		frappe.redirect_to_message(_('Invalid Token'),
			_('Seems token you are using is invalid!'),
			http_status_code=400, indicator_color='red')

		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect