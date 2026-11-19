# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Chats for people who are not signed in, with an agent marked Public.

A guest chat belongs to Guest and its tools run as Guest. It starts in Auto-approve, like a
trigger's chat, so a tool that asks for approval runs without it. They are all Guest, so the
chat is opened by the token `start` returns and by nothing else. Replies come live from the
realtime relay (`flow:subscribe` with the session and the token), or from `entries`."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Generator
from contextlib import contextmanager
from hmac import compare_digest
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.flow.lib.session import new_session, sync_with_retry
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.flow.doctype.flow_session.flow_session import FlowSession

# What one address may send in an hour, unless Flow Settings says otherwise: every message
# costs model calls, and no sign-in holds a script back.
HOUR = 60 * 60
MESSAGES_AN_HOUR = 30


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
# a chat is of no use without a message, so no more chats than messages
@rate_limit(limit=lambda: _messages_an_hour(), seconds=HOUR)
def start(agent: str) -> dict[str, str]:
	"""Start a chat with a public agent. `token` is given only here; every other call needs it."""
	token = secrets.token_urlsafe(32)
	with _as_guest():
		# like a trigger's chat: nobody is there to approve a call
		doc = new_session(agent, approval_mode="Auto-approve")
		doc.db_set("guest_token", _hash_token(token), update_modified=False)
	return {"session": doc.name, "token": token}


@frappe.whitelist(allow_guest=True, methods=["POST"], xss_safe=True)  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=lambda: _messages_an_hour(), seconds=HOUR)
def send(session: str, token: str, message: str) -> dict[str, str]:
	"""Send the guest's message and answer at once, without waiting for the reply."""
	doc = _load_session(session, token)
	with _as_guest():
		# a message sent the moment a run ends races that run's own syncs
		sync_with_retry(doc)
		run = doc.chat(message)
	return {"run": run.name}


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
def entries(session: str, token: str, since: int | str = 0) -> dict[str, Any]:
	"""The chat's log after entry `since`, for a guest who is not listening live."""
	since = cint(since)
	return _load_session(session, token).entries(since=since, path="all" if since else "active")


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def can_stream(session: str, token_hash: str) -> bool:
	"""Asked by the realtime relay, with the token's SHA-256: a GET's address may be logged,
	and the hash opens nothing else."""
	return _is_valid_hash(session, token_hash)


def _messages_an_hour() -> int:
	return frappe.db.get_single_value("Flow Settings", "guest_messages_per_hour") or MESSAGES_AN_HOUR


def _load_session(session: str, token: str) -> FlowSession:
	"""The chat `token` opens. A wrong token and a chat that is not there are refused alike."""
	if not _is_valid_token(session, token):
		frappe.throw(_("This chat is not available."), frappe.PermissionError, title=_("Not Available"))
	return frappe.get_doc("Flow Session", session)


def _is_valid_token(session: str, token: str) -> bool:
	return _is_valid_hash(session, _hash_token(token))


def _is_valid_hash(session: str, token_hash: str) -> bool:
	saved = frappe.db.get_value("Flow Session", {"name": session, "owner": "Guest"}, "guest_token")
	return bool(saved) and compare_digest(saved.encode(), token_hash.encode())


def _hash_token(token: str) -> str:
	return hashlib.sha256(token.encode()).hexdigest()


@contextmanager
def _as_guest() -> Generator[None]:
	"""Run as Guest whoever calls, then give a signed-in caller their own session back."""
	session = frappe.local.session
	user, sid, data = session.user, session.sid, session.data
	frappe.set_user("Guest")  # nosemgrep: frappe-setuser
	try:
		yield
	finally:
		frappe.set_user(user)  # nosemgrep: frappe-setuser
		session.sid, session.data = sid, data
