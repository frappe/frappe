# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
import frappe.share
from frappe.api import bulk_collaboration as routes
from frappe.cache_manager import clear_doctype_map
from frappe.desk.doctype.tag.tag import DocTags
from frappe.desk.form.assign_to import get as get_assignments
from frappe.desk.form.document_follow import get_document_followed_by_user
from frappe.tests import IntegrationTestCase
from frappe.utils.task_queue import _execute_task

PREFIX = "bulk47064"
USER = "bulk47064@example.com"
ASSIGNEE = "test@example.com"
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class TestBulkCollaboration(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(self.cleanup)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.form_dict.clear()
		self.names = [self.make_todo(i) for i in range(3)]

	def cleanup(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for doctype, field in (("ToDo", "description"), ("Event", "subject")):
			for name in frappe.get_all(doctype, {field: ["like", f"{PREFIX}%"]}, pluck="name"):
				frappe.delete_doc(doctype, name, force=True)
		# the rollback removed the rule but not the map the apply cached
		clear_doctype_map("Assignment Rule", "Event")
		frappe.db.delete("DocShare", {"user": USER})
		frappe.db.delete("Favourite", {"reference_doctype": "ToDo", "reference_name": ["in", self.names]})
		frappe.db.delete("Background Task", {"task_name": ["like", "%ToDo"]})
		frappe.db.commit()  # nosemgrep

	def make_todo(self, index: int) -> str:
		return frappe.get_doc({"doctype": "ToDo", "description": f"{PREFIX} {index}"}).insert().name

	def make_event(self, index: int = 0) -> str:
		return (
			frappe.get_doc(
				{
					"doctype": "Event",
					"subject": f"{PREFIX} event {index}",
					"starts_on": "2026-01-01 10:00:00",
					"event_type": "Private",
				}
			)
			.insert()
			.name
		)

	def make_user(self) -> str:
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{"doctype": "User", "email": USER, "first_name": "Bulk", "send_welcome_email": 0}
			).insert()
		frappe.db.set_value("User", USER, "bulk_actions", 1)
		frappe.clear_document_cache("User", USER)
		return USER

	def share_read_only(self) -> str:
		"""A gated user who can read the records through a share but not write or share them."""
		user = self.make_user()
		for name in self.names:
			frappe.share.add("ToDo", name, user=user, read=1)
		return user

	def body(self, names=None, **values):
		frappe.form_dict.clear()
		frappe.form_dict.update(names=self.names if names is None else names, **values)

	def assignees(self, name: str) -> list[str]:
		return [row.owner for row in get_assignments({"doctype": "ToDo", "name": name})]

	# Routes

	def test_every_route_reaches_its_function(self):
		from frappe.api import API_URL_MAP

		adapter = API_URL_MAP.bind("localhost")
		expected = {
			("POST", "bulk_assignments"): routes.bulk_assignments,
			("DELETE", "bulk_assignments"): routes.bulk_clear_assignments,
			("POST", "bulk_assignment_rule"): routes.bulk_assignment_rule,
			("POST", "bulk_tags"): routes.bulk_tags,
			("DELETE", "bulk_tags"): routes.bulk_remove_tags,
			("POST", "bulk_follows"): routes.bulk_follows,
			("DELETE", "bulk_follows"): routes.bulk_unfollows,
			("POST", "bulk_favourites"): routes.bulk_favourites,
			("DELETE", "bulk_favourites"): routes.bulk_unfavourites,
			("POST", "bulk_shares"): routes.bulk_shares,
			("POST", "bulk_seen"): routes.bulk_seen,
			("DELETE", "bulk_seen"): routes.bulk_unseen,
		}
		for (method, part), function in expected.items():
			# not `delete_doc` on a record named like the route
			endpoint, _args = adapter.match(f"/api/v2/document/ToDo/{part}", method=method)
			self.assertIs(endpoint, function)

	# Permissions: a read-only share tells the right a route checks from read

	def test_a_read_only_user_cannot_change_a_record_but_can_mark_it_seen(self):
		frappe.set_user(self.share_read_only())
		changes = (
			(routes.bulk_assignments, {"user": ASSIGNEE}),
			(routes.bulk_clear_assignments, {}),
			(routes.bulk_tags, {"tag": f"{PREFIX}-ro"}),
			(routes.bulk_remove_tags, {"tag": f"{PREFIX}-ro"}),
			(routes.bulk_shares, {"user": ASSIGNEE}),
		)
		for route, values in changes:
			self.body(**values)
			result = route("ToDo")
			self.assertEqual(result["done"], [], route.__name__)
			self.assertEqual(len(result["failed"]), 3, route.__name__)

		self.body()
		self.assertCountEqual(routes.bulk_seen("ToDo")["done"], self.names)

	# Selection

	def test_a_filter_selects_the_records_the_list_shows(self):
		frappe.form_dict.clear()
		frappe.form_dict.update(filters=[["description", "like", f"{PREFIX}%"]], tag=f"{PREFIX}-f")
		result = routes.bulk_tags("ToDo")
		self.assertCountEqual(result["done"], self.names)

	def test_a_missing_record_fails_alone(self):
		self.body(names=[*self.names[:1], "nope"], tag=f"{PREFIX}-m")
		result = routes.bulk_tags("ToDo")
		self.assertEqual(result["done"], self.names[:1])
		self.assertEqual(result["failed"][0]["name"], "nope")

	# Assignments

	def test_assign_adds_the_assignee_to_every_record(self):
		self.body(user=ASSIGNEE, description="look")
		result = routes.bulk_assignments("ToDo")

		self.assertCountEqual(result["done"], self.names)
		self.assertEqual(result["failed"], [])
		self.assertTrue(all(self.assignees(name) == [ASSIGNEE] for name in self.names))

	def test_assign_without_a_user_is_refused_before_any_record(self):
		self.body()
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_assignments("ToDo")

	def test_assign_rejects_an_unstringy_option(self):
		self.body(user=ASSIGNEE, priority=["High"])
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_assignments("ToDo")

	def test_clear_assignments_cancels_every_assignee(self):
		self.body(user=ASSIGNEE)
		routes.bulk_assignments("ToDo")

		self.body()
		result = routes.bulk_clear_assignments("ToDo")

		self.assertCountEqual(result["done"], self.names)
		self.assertTrue(all(self.assignees(name) == [] for name in self.names))

	def test_clear_assignments_of_an_unassigned_record_is_done(self):
		self.body(names=self.names[:1])
		self.assertEqual(routes.bulk_clear_assignments("ToDo")["done"], self.names[:1])

	def test_a_record_the_user_cannot_write_fails_alone(self):
		user = self.make_user()
		frappe.set_user(user)
		self.body(user=ASSIGNEE)
		result = routes.bulk_assignments("ToDo")

		self.assertEqual(result["done"], [])
		self.assertCountEqual([row["name"] for row in result["failed"]], self.names)
		frappe.set_user("Administrator")
		self.assertTrue(all(self.assignees(name) == [] for name in self.names))

	def test_a_user_without_the_gate_is_refused(self):
		user = self.make_user()
		frappe.db.set_value("User", user, "bulk_actions", 0)
		frappe.clear_document_cache("User", user)
		frappe.set_user(user)
		self.body(user=ASSIGNEE)
		with self.assertRaises(frappe.PermissionError):
			routes.bulk_assignments("ToDo")

	# Assignment rule

	def test_assignment_rule_is_applied_to_every_record(self):
		events = self.make_rule_and_events()
		self.body(names=events)
		with patch.object(routes, "apply_assignment_rules") as apply:
			result = routes.bulk_assignment_rule("Event")

		self.assertCountEqual(result["done"], events)
		self.assertCountEqual([call.kwargs["name"] for call in apply.call_args_list], events)

	def test_assignment_rule_assigns_the_records_it_matches(self):
		events = self.make_rule_and_events()
		self.body(names=events)
		self.assertCountEqual(routes.bulk_assignment_rule("Event")["done"], events)
		for event in events:
			todos = frappe.get_all(
				"ToDo", {"reference_type": "Event", "reference_name": event}, pluck="allocated_to"
			)
			self.assertEqual(todos, [ASSIGNEE])

	def test_assignment_rule_is_refused_when_the_doctype_has_no_enabled_rule(self):
		self.body()
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_assignment_rule("Event")

	def test_assignment_rule_needs_write_on_each_record(self):
		events = self.make_rule_and_events()
		user = self.make_user()
		for event in events:
			frappe.share.add("Event", event, user=user, read=1)
		frappe.set_user(user)
		self.body(names=events)
		with patch.object(routes, "apply_assignment_rules") as apply:
			result = routes.bulk_assignment_rule("Event")

		self.assertEqual(len(result["failed"]), 3)
		apply.assert_not_called()

	def make_rule_and_events(self) -> list[str]:
		events = [self.make_event(i) for i in range(3)]
		frappe.get_doc(
			{
				"doctype": "Assignment Rule",
				"name": f"{PREFIX} rule",
				"document_type": "Event",
				"assign_condition": "event_type == 'Private'",
				"rule": "Round Robin",
				"description": f"{PREFIX} rule",
				"priority": 0,
				"users": [{"user": ASSIGNEE}],
				"assignment_days": [{"day": day} for day in DAYS],
			}
		).insert()
		return events

	# Tags

	def test_add_tag_tags_every_record_and_remove_takes_it_off(self):
		self.body(tag=f"{PREFIX}-tag")
		self.assertCountEqual(routes.bulk_tags("ToDo")["done"], self.names)
		self.assertTrue(all(f"{PREFIX}-tag" in self.tags_of(name) for name in self.names))

		self.body(tag=f"{PREFIX}-tag")
		self.assertCountEqual(routes.bulk_remove_tags("ToDo")["done"], self.names)
		self.assertTrue(all(self.tags_of(name) == [] for name in self.names))

	def test_a_tag_with_a_comma_fails_every_record(self):
		self.body(tag="a,b")
		result = routes.bulk_tags("ToDo")
		self.assertEqual(len(result["failed"]), 3)
		self.assertEqual(result["done"], [])

	def test_add_tag_without_a_tag_is_refused(self):
		self.body()
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_tags("ToDo")

	def test_remove_tag_without_a_tag_is_refused(self):
		self.body()
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_remove_tags("ToDo")

	def tags_of(self, name: str) -> list[str]:
		return [tag for tag in (DocTags("ToDo").get_tags(name) or "").split(",") if tag]

	# Follow

	def test_follow_and_unfollow_a_doctype_that_tracks_changes(self):
		frappe.db.set_value("User", ASSIGNEE, "document_follow_notify", 1)
		frappe.set_user(ASSIGNEE)
		event = self.make_event()
		self.body(names=[event])
		self.assertEqual(routes.bulk_follows("Event")["done"], [event])
		self.assertTrue(self.follows("Event", event))

		self.assertEqual(routes.bulk_unfollows("Event")["done"], [event])
		self.assertFalse(self.follows("Event", event))

	def test_follow_fails_a_record_the_framework_quietly_skips(self):
		event = self.make_event()
		self.body(names=[event])
		result = routes.bulk_follows("Event")
		self.assertEqual(result["done"], [])
		self.assertEqual(result["failed"][0]["name"], event)

	def test_follow_is_refused_without_track_changes(self):
		self.body()
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_follows("Tag")

	def follows(self, doctype: str, name: str) -> bool:
		return bool(
			frappe.db.exists(
				"Document Follow",
				{"ref_doctype": doctype, "ref_docname": name, "user": frappe.session.user},
			)
		)

	# Favourite

	def test_favourite_and_unfavourite_the_records(self):
		self.body()
		self.assertCountEqual(routes.bulk_favourites("ToDo")["done"], self.names)
		self.assertCountEqual(self.starred(), self.names)

		# a second run changes nothing and fails nothing
		self.assertEqual(routes.bulk_favourites("ToDo")["failed"], [])
		self.assertEqual(len(self.starred()), 3)

		self.assertCountEqual(routes.bulk_unfavourites("ToDo")["done"], self.names)
		self.assertEqual(self.starred(), [])

	def test_favourites_are_the_session_users_own(self):
		self.body(names=self.names[:1])
		routes.bulk_favourites("ToDo")
		frappe.set_user(ASSIGNEE)
		self.body(names=self.names[:1])
		routes.bulk_unfavourites("ToDo")
		frappe.set_user("Administrator")
		self.assertEqual(self.starred(), self.names[:1])

	def test_favourite_by_filters(self):
		frappe.form_dict.clear()
		frappe.form_dict.update(filters=[["description", "like", f"{PREFIX}%"]])
		self.assertCountEqual(routes.bulk_favourites("ToDo")["done"], self.names)
		self.assertCountEqual(routes.bulk_unfavourites("ToDo")["done"], self.names)

	def test_favourite_fails_a_record_the_user_cannot_read(self):
		frappe.set_user(self.make_user())
		self.body()
		result = routes.bulk_favourites("ToDo")
		self.assertEqual(result["done"], [])
		self.assertEqual(len(result["failed"]), 3)

	def starred(self) -> list[str]:
		return frappe.get_all(
			"Favourite",
			{
				"user": frappe.session.user,
				"reference_doctype": "ToDo",
				"reference_name": ["in", self.names],
			},
			pluck="reference_name",
		)

	# Share

	def test_share_grants_the_user_access_with_the_rights(self):
		user = self.make_user()
		self.body(user=user, write=1)
		result = routes.bulk_shares("ToDo")

		self.assertCountEqual(result["done"], self.names)
		shares = frappe.get_all(
			"DocShare",
			{"user": user, "share_doctype": "ToDo", "share_name": ["in", self.names]},
			["read", "write", "share"],
		)
		self.assertEqual(len(shares), 3)
		self.assertTrue(all(share.read and share.write and not share.share for share in shares))

	def test_share_needs_the_share_right_on_each_record(self):
		frappe.set_user(self.make_user())
		self.body(user=ASSIGNEE)
		self.assertEqual(len(routes.bulk_shares("ToDo")["failed"]), 3)

	def test_share_that_withholds_read_is_refused(self):
		self.body(user=ASSIGNEE, read=0)
		result = routes.bulk_shares("ToDo")
		self.assertEqual(len(result["failed"]), 3)

	# Seen

	def test_seen_marks_and_unmarks_the_session_user(self):
		self.body()
		self.assertCountEqual(routes.bulk_seen("ToDo")["done"], self.names)
		self.assertTrue(all("Administrator" in self.seen_by(name) for name in self.names))

		self.assertCountEqual(routes.bulk_unseen("ToDo")["done"], self.names)
		self.assertTrue(all("Administrator" not in self.seen_by(name) for name in self.names))

	def test_seen_keeps_the_other_users(self):
		frappe.db.set_value("ToDo", self.names[0], "_seen", json.dumps([ASSIGNEE]))
		self.body(names=self.names[:1])
		routes.bulk_seen("ToDo")
		self.assertEqual(self.seen_by(self.names[0]), [ASSIGNEE, "Administrator"])

		routes.bulk_unseen("ToDo")
		self.assertEqual(self.seen_by(self.names[0]), [ASSIGNEE])

	def test_seen_is_refused_without_track_seen(self):
		self.body()
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_seen("Tag")
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_unseen("Tag")

	def test_seen_is_refused_on_a_single_doctype(self):
		self.body(names=["System Settings"])
		with self.assertRaises(frappe.ValidationError):
			routes.bulk_seen("System Settings")

	def test_seen_needs_read_on_each_record(self):
		frappe.set_user(self.make_user())
		self.body()
		self.assertEqual(len(routes.bulk_seen("ToDo")["failed"]), 3)

	def seen_by(self, name: str) -> list[str]:
		return json.loads(frappe.db.get_value("ToDo", name, "_seen") or "[]")

	# Background

	def test_a_background_run_carries_the_body_to_the_worker(self):
		self.body(user=ASSIGNEE)
		result = self.run_in_background(routes.bulk_assignments)
		self.assertCountEqual(result["done"], self.names)
		self.assertTrue(all(self.assignees(name) == [ASSIGNEE] for name in self.names))

	def test_a_background_tag_run_carries_the_tag(self):
		self.body(tag=f"{PREFIX}-bg")
		result = self.run_in_background(routes.bulk_tags)
		self.assertCountEqual(result["done"], self.names)
		self.assertTrue(all(f"{PREFIX}-bg" in self.tags_of(name) for name in self.names))

	def test_a_background_share_run_carries_the_rights(self):
		user = self.make_user()
		self.body(user=user, write=1)
		self.run_in_background(routes.bulk_shares)
		shares = frappe.get_all("DocShare", {"user": user, "share_name": ["in", self.names]}, ["write"])
		self.assertEqual([share.write for share in shares], [1, 1, 1])

	def run_in_background(self, route) -> dict:
		with patch.dict(frappe.conf, {"bulk_operation_async_threshold": 1}):
			with patch("frappe.utils.task_queue.frappe.enqueue") as enqueue:
				response = route("ToDo")
				frappe.db.commit()  # nosemgrep

		self.assertEqual(frappe.response.http_status_code, 202)
		options = {
			"queue",
			"timeout",
			"deduplicate",
			"job_id",
			"at_front",
			"now",
			"at_front_when_starved",
			"rq_retry",
		}
		kwargs = {key: value for key, value in enqueue.call_args.kwargs.items() if key not in options}
		frappe.form_dict.clear()  # the worker has no request body
		_execute_task(**kwargs)
		return frappe.parse_json(frappe.db.get_value("Background Task", response["task_id"], "result"))
