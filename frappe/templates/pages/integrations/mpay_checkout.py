# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
import frappe

from frappe import _


def get_context(context):
    context.no_cache = 1
    try:
        controller = frappe.get_doc('mPay Settings')
        payment_context = controller.get_payment_context(
            integration_request_id=frappe.form_dict['order_id']
        )
        context.payment_details = payment_context.get('data')
        context.gateway_url = payment_context.get('url')

    except Exception:
        frappe.log_error()
        frappe.redirect_to_message(
            _(
                'Invalid Token'
                'Seems token you are using is invalid!'
            ),
            http_status_code=400,
            indicator_color='red'
        )

        frappe.local.flags.redirect_location = frappe.local.response.location
        raise frappe.Redirect
