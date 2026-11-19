# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The save-time rule for an Act row a person or the site adds (`navigation_item_validators`)."""

import json
import re

import frappe
from frappe import _

# `shell.<item>` or an app's `shell.<app>.<item>`.
ACT_NAME = re.compile(r"shell\.[a-z0-9_]+(\.[a-z0-9_]+)?")

# What the boot budget allows an own row's payload: the Link's largest row is 249 B.
MAX_PAYLOAD_BYTES = 128


def validate_act_row(row: dict, container: str, scope: str, context):
	"""Refuse a payload that is no act, and store the rest in compact form."""
	label = frappe.bold(row["key"])
	payload = _payload_of(row, label)

	if row.get("opens_sidebar"):
		_refuse(_("An action can't open a sidebar."))

	if not isinstance(payload, dict) or "act" not in payload:
		_refuse(_("{0} needs an action to run.").format(label))

	if set(payload) - {"act", "value"}:
		_refuse(_("The saved value of {0} holds more than an action and its value.").format(label))

	if not (isinstance(payload["act"], str) and ACT_NAME.fullmatch(payload["act"])):
		_refuse(_("{0} does not name an action.").format(label))

	compact = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

	try:
		size = len(compact.encode())
	except UnicodeEncodeError:
		_refuse(_("The saved value of {0} is not valid text.").format(label))

	if size > MAX_PAYLOAD_BYTES:
		_refuse(_("This action's saved value is too long (over {0} bytes).").format(MAX_PAYLOAD_BYTES))

	row["payload"] = compact


# The hook's contract: the module it names holds `validate_own_row`.
validate_own_row = validate_act_row


def _payload_of(row: dict, label: str):
	payload = row.get("payload")

	if not isinstance(payload, str):
		return payload

	try:
		return json.loads(payload)
	except ValueError:
		_refuse(_("The payload of {0} is not an object.").format(label))


def _refuse(message: str):
	frappe.throw(message, title=_("Not an Arrangement"))
