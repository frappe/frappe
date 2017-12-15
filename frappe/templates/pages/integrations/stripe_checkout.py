# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint
import json

no_cache = 1
no_sitemap = 1

expected_keys = ('amount', 'title', 'description', 'reference_doctype', 'reference_docname',
	'payer_name', 'payer_email', 'order_id', 'currency')

def get_context(context):
	context.no_cache = 1
	context.publishable_key = get_api_key()

	# all these keys exist in form_dict
	if not (set(expected_keys) - set(frappe.form_dict.keys())):
		for key in expected_keys:
			context[key] = frappe.form_dict[key]

		context['amount'] = flt(context['amount'])

	else:
		frappe.redirect_to_message(_('Some information is missing'),
			_('Looks like someone sent you to an incomplete URL. Please ask them to look into it.'))
		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect

def get_api_key():
	publishable_key = frappe.db.get_value("Stripe Settings", None, "publishable_key")
	if cint(frappe.form_dict.get("use_sandbox")):
		publishable_key = frappe.conf.sandbox_publishable_key

	return publishable_key

@frappe.whitelist(allow_guest=True)
def make_payment(stripe_token_id, data, reference_doctype=None, reference_docname=None):
	data = json.loads(data)

	data.update({
		"stripe_token_id": stripe_token_id
	})

	data =  frappe.get_doc("Stripe Settings").create_request(data)
	frappe.db.commit()
	return data