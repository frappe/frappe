from __future__ import unicode_literals
import frappe


def get_context(context):
		if frappe.form_dict['user_email']:
			context.hello="hello"
			print("++++++++++++++++++++++++++++++++++sucess++++++++++++++++++++++++++++++++++++++++++++++")