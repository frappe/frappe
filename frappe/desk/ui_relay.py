# UI RELAY — a server call reaches the person's open desk v2 tab and gets its answer back.
# Out: `publish_realtime` to the user's room. Back: the tab's `reply`, through a Redis list per call id.

import json
import secrets
import time
from typing import Any

import frappe
from frappe import _
from frappe.auth import get_oauth_client_name
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

EVENT = "ui_relay"
OPS = ("acts", "state", "dialogs", "run", "wait")
FIELD = "agent_ui_relay"

CALL_WAIT = 25  # seconds one HTTP call holds a worker; frappectl times out at 60
TAB_WAIT = 1  # seconds the tabs get to answer a hello
KEEP = 15 * 60  # seconds a result stays under its call id
CALLS_PER_MINUTE = 60
REPLIES_PER_MINUTE = 600  # a tab answers each call twice at most, and each hello once
MAX_REPLY_BYTES = 1_000_000
MAX_REPLIES = 20  # per call id

Json = dict | list | str | int | float | bool | None


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=CALLS_PER_MINUTE, seconds=60, ip_based=False, user_based=True)
def tabs() -> list[dict]:
	"""The tabs of this user that listen: `{tab, route, title, focused_at}`, the last focused first."""
	user = _relay_user()
	return _hello(user)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=CALLS_PER_MINUTE, seconds=60, ip_based=False, user_based=True)
def call(
	op: str,
	tab: str | None = None,
	act: str | None = None,
	args: Json = None,
	call_id: str | None = None,
) -> dict:
	"""Runs `op` (a `window.desk` member) in the user's open tab and waits up to about 25 s for the answer.

	No `tab`: the tab focused last. `wait` needs the `call_id` of an earlier call that returned `waiting_for_user`.
	"""
	user = _relay_user()
	if op not in OPS:
		frappe.throw(_("op must be one of {0}.").format(", ".join(OPS)), frappe.ValidationError)

	if op == "wait":
		if not call_id:
			frappe.throw(_("wait needs the call_id of the call to wait for."), frappe.ValidationError)
		return _await(call_id, None)

	found = _find_tab(user, tab)
	if not found:
		return _failure("tab_not_found", _("No open tab answered. Run `fr ui tabs` to list the tabs."), tab)

	call_id = secrets.token_urlsafe(16)
	frappe.publish_realtime(
		EVENT,
		{
			"call_id": call_id,
			"op": op,
			"tab": found["tab"],
			"act": act,
			"args": args,
			"client": get_oauth_client_name(),  # the registered name the person approved, not the client id
		},
		user=user,
	)
	return _await(call_id, found)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=REPLIES_PER_MINUTE, seconds=60, ip_based=False, user_based=True)
def reply(call_id: str, result: dict, tab: str | None = None, final: bool | int = True) -> None:
	"""Called only by a tab. The key holds the session user, so a tab answers only its own user's calls."""
	_relay_user()
	_check_id(call_id)
	payload = json.dumps({"final": bool(cint(final)), "tab": tab, "result": result})
	key = _key(call_id)
	if len(payload) > MAX_REPLY_BYTES or frappe.cache.llen(key) >= MAX_REPLIES:
		frappe.throw(_("The reply is too large or there are too many for this call."), frappe.ValidationError)
	frappe.cache.rpush(key, payload)
	frappe.cache.expire_key(key, KEEP)


def _relay_user() -> str:
	user = frappe.session.user
	if not cint(frappe.get_cached_value("User", user, FIELD)):
		frappe.throw(
			_("This user has not allowed agents to drive their open tabs."),
			frappe.PermissionError,
		)
	return user


def _find_tab(user: str, tab: str | None) -> dict | None:
	"""The named tab, or the one focused last; `None` when no listening tab answers in time."""
	found = _hello(user, want=tab)
	if tab:
		return next((item for item in found if item["tab"] == tab), None)
	return found[0] if found else None


def _hello(user: str, want: str | None = None) -> list[dict]:
	"""Asks every listening tab to name itself; stops early when `want` answers."""
	call_id = secrets.token_urlsafe(16)
	frappe.publish_realtime(EVENT, {"call_id": call_id, "op": "tabs"}, user=user)

	answers: dict[str, dict] = {}
	deadline = time.monotonic() + TAB_WAIT
	while (left := deadline - time.monotonic()) > 0:
		popped = _pop(call_id, left)
		if not popped:
			break
		answer = popped["result"]
		if isinstance(answer, dict) and isinstance(answer.get("tab"), str):  # an old tab may answer badly
			answers[answer["tab"]] = answer
			if want and answer["tab"] == want:
				break

	frappe.cache.delete_key(_key(call_id))
	return sorted(answers.values(), key=lambda item: item.get("focused_at") or 0, reverse=True)


def _await(call_id: str, found: dict | None) -> dict:
	"""The call's first answer, or `waiting_for_user` when the tab has not ended it in about 25 s."""
	_check_id(call_id)
	deadline = time.monotonic() + CALL_WAIT
	while (left := deadline - time.monotonic()) > 0:
		popped = _pop(call_id, left)
		if not popped:
			break
		if popped["final"]:
			_keep(call_id, popped)
		return _with_call(popped["result"], call_id, popped.get("tab"))

	message = _("The tab has not finished. Call wait with this call id again.")
	return _failure("waiting_for_user", message, found and found["tab"], found and found["route"], call_id)


def _with_call(result: dict, call_id: str, tab: str | None) -> dict:
	error = result.get("error")
	if isinstance(error, dict) and error.get("code") == "waiting_for_user":
		error["call"] = call_id
	if tab:
		result["tab"] = tab
	return result


def _keep(call_id: str, popped: dict):
	"""A final result stays for a late `wait`: put it back with its time to live."""
	key = _key(call_id)
	frappe.cache.lpush(key, json.dumps(popped))
	frappe.cache.expire_key(key, KEEP)


def _pop(call_id: str, timeout: float) -> dict | None:
	popped = frappe.cache.blpop(_key(call_id), timeout=timeout)
	return json.loads(popped[1]) if popped else None


def _failure(code: str, message: str, tab=None, route=None, call: str | None = None) -> dict:
	error: dict[str, Any] = {"code": code, "message": message}
	if call:
		error["call"] = call
	return {"ok": False, "error": error, "tab": tab, "route": route}


def _key(call_id: str) -> str:
	return f"user:{frappe.session.user}:ui_reply:{call_id}"


def _check_id(call_id: str):
	if not 16 <= len(call_id) <= 32 or not call_id.replace("-", "").replace("_", "").isalnum():
		frappe.throw(_("Not a call id."), frappe.ValidationError)
