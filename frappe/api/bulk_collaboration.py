"""The collaboration bulk routes: each takes the body of its per-document route in `frappe.api.collaboration`.

`POST /document/<doctype>/bulk_<part>` adds, `DELETE` removes, over `names` or `filters` and `or_filters`.
A record goes through `collaboration.load`, so it needs the right the per-document route needs.
"""

import json

import frappe
from frappe import _
from frappe.api import collaboration
from frappe.api.bulk import BulkAction, run_bulk
from frappe.automation.doctype.assignment_rule.assignment_rule import apply as apply_assignment_rules
from frappe.desk.form import assign_to
from frappe.desk.form.document_follow import is_document_followed
from frappe.utils import cint

SHARE_RIGHTS = ("read", "write", "submit", "share")
# the body key that names what to remove, where the per-document route takes it in its path
REMOVE_KEY = {"tags": "tag"}


def bulk_assignments(doctype: str):
	"""POST /document/<doctype>/bulk_assignments

	Body: `names`, or `filters` and `or_filters`, and the body of `POST .../assignments`: `user`,
	and `description`, `priority` and `date` when set. Result: `{total, done, failed}` as in `run_bulk`.
	"""
	return run_part(ASSIGN, doctype, "assignments")


def bulk_clear_assignments(doctype: str):
	"""DELETE /document/<doctype>/bulk_assignments: cancels every assignment on the records."""
	return run_bulk(CLEAR_ASSIGNMENTS, doctype)


def bulk_assignment_rule(doctype: str):
	"""POST /document/<doctype>/bulk_assignment_rule: applies the doctype's Assignment Rules to the records."""
	return run_bulk(APPLY_ASSIGNMENT_RULE, doctype)


def bulk_tags(doctype: str):
	"""POST /document/<doctype>/bulk_tags. Body: `tag`, and `color` for a new Tag."""
	return run_part(ADD_TAG, doctype, "tags")


def bulk_remove_tags(doctype: str):
	"""DELETE /document/<doctype>/bulk_tags. Body: `tag`."""
	return run_part(REMOVE_TAG, doctype, "tags", adding=False)


def bulk_follows(doctype: str):
	"""POST /document/<doctype>/bulk_follows: the session user follows the records. Refused without `track_changes`."""
	return run_part(FOLLOW, doctype, "follows")


def bulk_unfollows(doctype: str):
	"""DELETE /document/<doctype>/bulk_follows"""
	return run_part(UNFOLLOW, doctype, "follows", adding=False)


def bulk_favourites(doctype: str):
	"""POST /document/<doctype>/bulk_favourites: the session user stars the records."""
	return run_part(FAVOURITE, doctype, "favourites")


def bulk_unfavourites(doctype: str):
	"""DELETE /document/<doctype>/bulk_favourites"""
	return run_part(UNFAVOURITE, doctype, "favourites", adding=False)


def bulk_shares(doctype: str):
	"""POST /document/<doctype>/bulk_shares. Body: `user` ("everyone" for all), and `write`, `submit`, `share` as 0 or 1."""
	return run_part(SHARE, doctype, "shares", extra=SHARE_RIGHTS)


def bulk_seen(doctype: str):
	"""POST /document/<doctype>/bulk_seen: marks the records seen by the session user. Refused without `track_seen`."""
	return run_bulk(MARK_SEEN, doctype)


def bulk_unseen(doctype: str):
	"""DELETE /document/<doctype>/bulk_seen: marks the records unseen by the session user."""
	return run_bulk(MARK_UNSEEN, doctype)


def run_part(
	action: BulkAction,
	doctype: str,
	part: str,
	*,
	adding: bool = True,
	extra: tuple[str, ...] = (),
):
	"""Validate the body once as the per-document route does, then run it on each record.

	The body goes in `params`: a background run has no request to read it from.
	"""
	body = collaboration.read_body(part, adding=adding)
	keys = (*collaboration.REQUIRED_BODY[part], *collaboration.OPTIONAL_BODY.get(part, ()), *extra)
	picked = {name: body[name] for name in keys if name in body}
	return run_bulk(action, doctype, params={"part": part, "body": picked})


def add_to_part(doctype: str, name: str, part: str, body: dict):
	collaboration.ADD[part](collaboration.load(doctype, name, part), body)


def remove_from_part(doctype: str, name: str, part: str, body: dict):
	key = body.get(REMOVE_KEY.get(part))
	collaboration.REMOVE[part](collaboration.load(doctype, name, part), key)


def follow_one(doctype: str, name: str, part: str, body: dict):
	"""Follow, or fail the record: the framework call quietly does nothing for the Administrator."""
	add_to_part(doctype, name, part, body)
	if not is_document_followed(doctype, name, frappe.session.user):
		frappe.throw(_("{0} cannot follow {1}.").format(frappe.session.user, name))


def clear_assignments_one(doctype: str, name: str):
	collaboration.load(doctype, name, "assignments")
	assign_to.clear(doctype, name)


def apply_assignment_rule_one(doctype: str, name: str):
	collaboration.load(doctype, name, "assignments")
	apply_assignment_rules(doctype=doctype, name=name)


def mark_seen_one(doctype: str, name: str):
	set_seen(doctype, name, add=True)


def mark_unseen_one(doctype: str, name: str):
	set_seen(doctype, name, add=False)


def set_seen(doctype: str, name: str, add: bool):
	"""Add the session user to the record's `_seen`, or take them out."""
	frappe.get_doc(doctype, name).check_permission("read")
	user = frappe.session.user
	seen = frappe.parse_json(frappe.db.get_value(doctype, name, "_seen") or "[]")
	if add:
		updated = seen if user in seen else [*seen, user]
	else:
		updated = [seen_by for seen_by in seen if seen_by != user]
	if updated != seen:
		frappe.db.set_value(doctype, name, "_seen", json.dumps(updated), update_modified=False)


def refuse_without_track_changes(doctype: str, params: dict):
	if not cint(frappe.get_meta(doctype).track_changes):
		frappe.throw(_("{0} does not track changes, so its records cannot be followed.").format(doctype))


def refuse_without_assignment_rule(doctype: str, params: dict):
	if not frappe.db.exists("Assignment Rule", {"document_type": doctype, "disabled": 0}):
		frappe.throw(_("{0} has no enabled Assignment Rule.").format(doctype))


def refuse_without_track_seen(doctype: str, params: dict):
	meta = frappe.get_meta(doctype)
	if meta.issingle or not cint(meta.track_seen):
		frappe.throw(_("{0} does not track who has seen a record.").format(doctype))


ASSIGN = BulkAction("Assign", add_to_part)
CLEAR_ASSIGNMENTS = BulkAction("Clear Assignment", clear_assignments_one)
APPLY_ASSIGNMENT_RULE = BulkAction(
	"Apply Assignment Rule", apply_assignment_rule_one, check=refuse_without_assignment_rule
)
ADD_TAG = BulkAction("Add Tag", add_to_part)
REMOVE_TAG = BulkAction("Remove Tag", remove_from_part)
FOLLOW = BulkAction("Follow", follow_one, check=refuse_without_track_changes)
UNFOLLOW = BulkAction("Unfollow", remove_from_part, check=refuse_without_track_changes)
FAVOURITE = BulkAction("Favourite", add_to_part)
UNFAVOURITE = BulkAction("Unfavourite", remove_from_part)
SHARE = BulkAction("Share", add_to_part)
MARK_SEEN = BulkAction("Mark as Seen", mark_seen_one, check=refuse_without_track_seen)
MARK_UNSEEN = BulkAction("Mark as Unseen", mark_unseen_one, check=refuse_without_track_seen)
