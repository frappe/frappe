# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _, msgprint, throw
from frappe.model.document import Document
from frappe.utils import nowdate


class SMSSettings(Document):
	_DOCTYPE_NAME = "SMS Settings"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.core.doctype.sms_parameter.sms_parameter import SMSParameter
		from frappe.types import DF

		message_parameter: DF.Data
		parameters: DF.Table[SMSParameter]
		receiver_parameter: DF.Data
		roles: DF.Table[HasRole]
		sms_gateway_url: DF.SmallText
		sms_rate_limit: DF.Int
		use_post: DF.Check
	# end: auto-generated types

	pass


def validate_receiver_nos(receiver_list):
	validated_receiver_list = []
	for d in receiver_list:
		if not d:
			continue

		# remove invalid character
		for x in [" ", "-", "(", ")"]:
			d = d.replace(x, "")

		validated_receiver_list.append(d)

	if not validated_receiver_list:
		throw(_("Please enter valid mobile nos"))

	return validated_receiver_list


@frappe.whitelist()
def get_contact_number(contact_name: str, ref_doctype: str, ref_name: str):
	"Return mobile number of the given contact."
	frappe.has_permission("Contact", doc=contact_name, throw=True)
	frappe.has_permission(ref_doctype, doc=ref_name, throw=True)

	is_linked = frappe.db.exists(
		"Dynamic Link",
		{
			"parenttype": "Contact",
			"parent": contact_name,
			"link_doctype": ref_doctype,
			"link_name": ref_name,
		},
	)
	if not is_linked:
		return ""

	contact = frappe.db.get_value("Contact", contact_name, ["mobile_no", "phone"], as_dict=True)

	return (contact and (contact.mobile_no or contact.phone)) or ""


def get_sms_ratelimit() -> int:
	return frappe.db.get_single_value("SMS Settings", "sms_rate_limit") or 60


def enforce_per_user_sms_ratelimit():
	cache_key = frappe.cache.make_key("sms-rate-limit", user=True)
	# incrby is atomic, unlike a get + set pair, so concurrent requests can't clobber each other's count
	count = frappe.cache.incrby(cache_key, 1)
	# nx=True only sets the TTL if the key doesn't already have one, so calling this on every
	# request is safe and keeps a fixed (not sliding) window instead of resetting it each time
	frappe.cache.expire(cache_key, 60 * 60, nx=True)

	if count > get_sms_ratelimit():
		frappe.throw(
			_(
				"You hit the rate limit because of too many requests. Please try after sometime, "
				"or ask your System Manager to change the Rate Limit in SMS Settings."
			),
			frappe.RateLimitExceededError,
		)


def is_permitted_to_send_sms() -> bool:
	"""Return True if no roles are configured, or the current user has one of them."""
	from frappe.utils import has_common

	if frappe.session.user == "Guest" or frappe.utils.user.is_website_user():
		return False

	allowed = [
		d.role for d in frappe.get_all("Has Role", fields=["role"], filters={"parent": "SMS Settings"})
	]
	if not allowed:
		return True

	return bool(has_common(frappe.get_roles(), allowed))


@frappe.whitelist()
def send_sms(receiver_list: str | list[str], msg: str, sender_name: str = "", success_msg: bool = True):
	if not is_permitted_to_send_sms():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	enforce_per_user_sms_ratelimit()

	send_sms_hook_methods = frappe.get_hooks("send_sms")
	if send_sms_hook_methods:
		return frappe.get_attr(send_sms_hook_methods[-1])(receiver_list, msg, sender_name, success_msg)

	import json

	if isinstance(receiver_list, str):
		receiver_list = json.loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]

	receiver_list = validate_receiver_nos(receiver_list)

	arg = {
		"receiver_list": receiver_list,
		"message": frappe.safe_decode(msg).encode("utf-8"),
		"success_msg": success_msg,
	}

	if frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
		send_via_gateway(arg)
	else:
		msgprint(_("Please Update SMS Settings"))


def send_via_gateway(arg):
	ss = frappe.get_doc("SMS Settings", "SMS Settings")
	headers = get_headers(ss)
	use_json = headers.get("Content-Type") == "application/json"

	message = frappe.safe_decode(arg.get("message"))
	args = {ss.message_parameter: message}
	for d in ss.get("parameters"):
		if not d.header:
			args[d.parameter] = d.value

	success_list = []
	for d in arg.get("receiver_list"):
		args[ss.receiver_parameter] = d
		status = send_request(ss.sms_gateway_url, args, headers, ss.use_post, use_json)

		if 200 <= status < 300:
			success_list.append(d)

	if len(success_list) > 0:
		args.update(arg)
		create_sms_log(args, success_list)
		if arg.get("success_msg"):
			frappe.msgprint(_("SMS sent successfully"))


def get_headers(sms_settings=None):
	if not sms_settings:
		sms_settings = frappe.get_doc("SMS Settings", "SMS Settings")

	headers = {"Accept": "text/plain, text/html, */*"}
	for d in sms_settings.get("parameters"):
		if d.header == 1:
			headers.update({d.parameter: d.value})

	return headers


def send_request(gateway_url, params, headers=None, use_post=False, use_json=False):
	import requests

	if not headers:
		headers = get_headers()
	kwargs = {"headers": headers}

	if use_json:
		kwargs["json"] = params
	elif use_post:
		kwargs["data"] = params
	else:
		kwargs["params"] = params

	if use_post:
		response = requests.post(gateway_url, **kwargs)
	else:
		response = requests.get(gateway_url, **kwargs)
	response.raise_for_status()
	return response.status_code


# Create SMS Log
# =========================================================
def create_sms_log(args, sent_to):
	# SMS Log doctype was removed; skip silently if it isn't available
	# (apps that still ship it will continue to log).
	if not frappe.db.exists("DocType", "SMS Log"):
		return
	sl = frappe.new_doc("SMS Log")
	sl.sent_on = nowdate()
	sl.message = args["message"].decode("utf-8")
	sl.no_of_requested_sms = len(args["receiver_list"])
	sl.requested_numbers = "\n".join(args["receiver_list"])
	sl.no_of_sent_sms = len(sent_to)
	sl.sent_to = "\n".join(sent_to)
	sl.flags.ignore_permissions = True
	sl.save()
