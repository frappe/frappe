# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import braintree


class BraintreeSettings(Document):
    supported_currencies = [
        "AED", "ALL", "ANG", "ARS", "AUD", "AWG", "BBD", "BDT", "BIF", "BMD", "BND",
        "BOB", "BRL", "BSD", "BWP", "BZD", "CAD", "CHF", "CLP", "CNY", "COP", "CRC", "CVE", "CZK", "DJF",
        "DKK", "DOP", "DZD", "EGP", "ETB", "EUR", "FJD", "FKP", "GBP", "GIP", "GMD", "GNF", "GTQ", "GYD",
        "HKD", "HNL", "HRK", "HTG", "HUF", "IDR", "ILS", "INR", "ISK", "JMD", "JPY", "KES", "KHR", "KMF",
        "KRW", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD", "MAD", "MDL", "MNT", "MOP", "MRO", "MUR", "MVR",
        "MWK", "MXN", "MYR", "NAD", "NGN", "NIO", "NOK", "NPR", "NZD", "PAB", "PEN", "PGK", "PHP", "PKR",
        "PLN", "PYG", "QAR", "RUB", "SAR", "SBD", "SCR", "SEK", "SGD", "SHP", "SLL", "SOS", "STD", "SVC",
        "SZL", "THB", "TOP", "TTD", "TWD", "TZS", "UAH", "UGX", "USD", "UYU", "UZS", "VND", "VUV", "WST",
        "XAF", "XOF", "XPF", "YER", "ZAR"
    ]

    def validate(self):
        create_payment_gateway('Braintree')
        call_hook_method('payment_gateway_enabled', gateway='Braintree')
        if not self.flags.ignore_mandatory:
            self.configure_braintree()

    def configure_braintree(self):
        braintree.Configuration.configure(
            braintree.Environment.Sandbox,
              merchant_id= self.merchant_id,
              public_key=self.public_key,
              private_key=self.private_key
            )

    def validate_transaction_currency(self, currency):
        if currency not in self.supported_currencies:
            frappe.throw(_("Please select another payment method. Stripe does not support transactions in currency '{0}'").format(currency))

    def create_payment_request(self, data):
        self.data = frappe._dict(data)

        try:
            self.integration_request = create_request_log(self.data, "Host", "Stripe")
            return self.create_charge_on_braintree()

        except Exception:
            frappe.log_error(frappe.get_traceback())
            return{
                "redirect_to": frappe.redirect_to_message(_('Server Error'), _("Seems issue with server's braintree config. Don't worry, in case of failure amount will get refunded to your account.")),
                "status": 401
            }

    def create_charge_on_braintree(self):

        try:
            self.result = braintree.Transaction.sale({
                "amount": "1000.00",
                "payment_method_nonce": nonce_from_the_client,
                "options": {
                    "submit_for_settlement": True
                }
            })
        except:
            pass

        if self.result.is_success:
            print("success!: " + result.transaction.id)
        elif self.result.transaction:
            print("Error processing transaction:")
            print("  code: " + result.transaction.processor_response_code)
            print("  text: " + result.transaction.processor_response_text)
        else:
            for error in self.result.errors.deep_errors:
                print("attribute: " + error.attribute)
                print("  code: " + error.code)
                print("  message: " + error.message)

        print(self.result)
