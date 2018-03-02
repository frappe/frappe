# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ExotelSettings(Document):
	pass

@frappe.whitelist(allow_guest=True)
def handle_incoming_call(*args, **kwargs):
	 """ Handles incoming calls in telephony service. """
	r = frappe.form_dict

	try:
		if args or kwargs:
			content = args or kwargs

			comm = frappe.new_doc("Communication")
			comm.subject = "Incoming Call " + frappe.utils.get_datetime_str(frappe.utils.get_datetime())
			comm.send_email = 0
			comm.communication_medium = "Phone"
			comm.phone_no = content.get("From")
			comm.comment_type = "Info"
			comm.communication_type = "Communication"
			comm.status = "Open"
			comm.sent_or_received = "Received"
			comm.content = "Incoming Call " + frappe.utils.get_datetime_str(frappe.utils.get_datetime()) + "<br>" + content + "<br> R=" + r
			comm.communication_date = content.get("StartTime")
			comm.sid = content.get("CallSid")
			# identify and add exophone

			comm.save(ignore_permissions=True)
			frappe.db.commit()

			return comm
	except Exception as e:
		frappe.log_error(message=e, title="Error log for incoming call")

@frappe.whitelist(allow_guest=True)
def capture_call_details(*args, **kwargs):
	 """ Captures post-call details in telephony service. """

	# requests.get('https://{0}:{1}@api.exotel.com/v1/Accounts/{0}/Calls/callsid'.format(credentials.exotel_sid,credentials.exotel_token), data=data)
	try:
		if args or kwargs:
			content = args or kwargs

			call = frappe.get_all("Communication", filters={"sid":content.get("CallSid")}, fields=["name"])
			comm = frappe.get_doc("Communication",call[0].name)
			comm.recording_url = content.get("RecordingUrl")
			comm.save(ignore_permissions=True)
			frappe.db.commit()

			return comm
	except Exception as e:
		frappe.log_error(message=e, title="Error in capturing call details")

@frappe.whitelist()
def handle_outgoing_call(From, To, CallerId, StatusCallback=None):
	"""Handles outgoing calls in telephony service.
	
	:param From: Number of exophone or call center member
	:param To: Number of customer
	:param CallerId: Exophone number	
	"""
	r = frappe.form_dict
	try:
		credentials = frappe.get_doc("Exotel Settings")	
		import requests

		data = {
			'From': From,
			'To': To,
			'CallerId': CallerId
		}
		response = requests.post('https://{0}:{1}@api.exotel.com/v1/Accounts/{0}/Calls/connect'.format(credentials.exotel_sid,credentials.exotel_token), data=data)

		comm = frappe.new_doc("Communication")
		comm.subject = "Outgoing Call " + frappe.utils.get_datetime_str(frappe.utils.get_datetime())
		comm.send_email = 0
		comm.communication_medium = "Phone"
		# comm.phone_no = content.get("From")
		comm.comment_type = "Info"
		comm.communication_type = "Communication"
		comm.status = "Open"
		comm.sent_or_received = "Sent"
		comm.content = "Outgoing Call " + frappe.utils.get_datetime_str(frappe.utils.get_datetime()) + "<br>" + content + "<br> R=" + r
		comm.communication_date = content.get("StartTime")
		comm.recording_url = content.get("RecordingUrl")
		comm.sid = content.get("CallSid")

		comm.save(ignore_permissions=True)
		frappe.db.commit()

		return comm
	except Exception as e:
		frappe.log_error(message=e, title="Error log for outgoing call")