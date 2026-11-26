# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from werkzeug.http import parse_cookie

import frappe
import frappe.exceptions
from frappe.client import set_value
from frappe.core.doctype.user.user import (
	User,
	bulk_add_roles,
	bulk_remove_roles,
	change_password,
	create_contact,
	get_all_roles,
	get_perm_info,
	handle_password_test_fail,
	needs_password_setup,
	reset_password,
	rewrite_owner_fields,
	set_first_password,
	sign_up,
	test_password_strength,
	update_password,
	verify_password,
)
from frappe.database import get_db
from frappe.desk.notifications import extract_mentions
from frappe.frappeclient import FrappeClient
from frappe.model.delete_doc import delete_doc
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import change_settings
from frappe.tests.test_api import FrappeAPITestCase
from frappe.tests.test_query_builder import db_type_is, unimplemented_for
from frappe.tests.utils import toggle_test_mode
from frappe.tests.utils.test_capabilities import TestService, requires_test_service
from frappe.utils import (
	add_days,
	add_to_date,
	get_email_addresses,
	get_url,
	get_user_by_email,
	get_user_display_id,
	getdate,
	now_datetime,
	sha256_hash,
	today,
)
from frappe.utils.data import orjson_dumps
from frappe.www.login import sanitize_redirect

user_module = frappe.core.doctype.user.user


class TestUser(IntegrationTestCase):
	def setUp(self):
		counter_prefix = "rl:frappe.core.doctype.user.user.update_password:"
		frappe.cache.delete_keys(counter_prefix)
		self.addCleanup(frappe.cache.delete_keys, counter_prefix)

	def tearDown(self):
		# disable password strength test
		frappe.db.set_single_value("System Settings", "enable_password_policy", 0)
		frappe.db.set_single_value("System Settings", "minimum_password_score", "")
		frappe.db.set_single_value("System Settings", "password_reset_limit", 3)
		frappe.set_user("Administrator")

	def test_role_listing_requires_role_read(self):
		desk_user = frappe.get_doc(
			doctype="User",
			email="roles_desk_user@example.com",
			first_name="Desk",
			roles=[{"role": "_Test Role"}],
			send_welcome_email=0,
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "User", desk_user.name, force=True)

		# a desk user without read on Role
		frappe.set_user(desk_user.name)
		self.assertRaises(frappe.PermissionError, get_all_roles)
		self.assertRaises(frappe.PermissionError, get_perm_info, "System Manager")

		frappe.set_user("test@example.com")
		self.assertIn("System Manager", get_all_roles())
		self.assertTrue(get_perm_info("System Manager"))

	@staticmethod
	def reset_password(user) -> str:
		link = user._reset_password()
		return parse_qs(urlparse(link).query)["key"][0]

	def test_my_space_is_offered_only_when_asked_for(self):
		"""The user menu's way into the Private shell is off until somebody turns it on, so a first
		time user is not shown a place they have put nothing in. It travels with the other per-user
		desk toggles, so the desk reads it the way it reads the search bar.
		"""
		from frappe.boot import get_desk_settings

		user = frappe.get_doc(
			doctype="User",
			email=frappe.generate_hash() + "@example.com",
			first_name="Space",
			roles=[{"role": "System Manager"}],
		).insert()
		self.addCleanup(frappe.delete_doc, "User", user.name, force=True, ignore_missing=True)

		frappe.set_user(user.name)
		self.assertEqual(get_desk_settings().show_my_space, 0)

		user.db_set("show_my_space", 1)
		frappe.clear_cache(user=user.name)
		self.assertEqual(get_desk_settings().show_my_space, 1)

	def test_dock_pinned_until_floated(self):
		"""The dock starts pinned beside the sidebar. Floating it off the left edge is a per-user
		desk toggle, so the desk reads it from the boot's desk settings like the others.
		"""
		from frappe.boot import get_desk_settings

		user = frappe.get_doc(
			doctype="User",
			email=frappe.generate_hash() + "@example.com",
			first_name="Dock",
			roles=[{"role": "_Test Role 2"}],
		).insert()
		self.addCleanup(frappe.delete_doc, "User", user.name, force=True, ignore_missing=True)

		frappe.set_user(user.name)
		self.assertEqual(get_desk_settings().dock_mode, "Pinned")

		set_value("User", user.name, "dock_mode", "Floating")
		frappe.clear_cache(user=user.name)
		self.assertEqual(get_desk_settings().dock_mode, "Floating")

	def test_user_type(self):
		user_id = frappe.generate_hash() + "@example.com"
		new_user = frappe.get_doc(doctype="User", email=user_id, first_name="Tester").insert()
		self.assertEqual(new_user.user_type, "Website User")

		# social login userid for frappe
		self.assertTrue(new_user.social_logins[0].userid)
		self.assertEqual(new_user.social_logins[0].provider, "frappe")

		# role with desk access
		new_user.add_roles("_Test Role 2")
		new_user.save()
		self.assertEqual(new_user.user_type, "System User")

		# clear role
		new_user.roles = []
		new_user.save()
		self.assertEqual(new_user.user_type, "Website User")

		# role without desk access
		new_user.add_roles("_Test Role 4")
		new_user.save()
		self.assertEqual(new_user.user_type, "Website User")

		delete_contact(new_user.name)
		frappe.delete_doc("User", new_user.name)

	def test_frappe_social_login_userid_is_immutable(self):
		user_id = frappe.generate_hash() + "@example.com"
		user = frappe.get_doc(doctype="User", email=user_id, first_name="Tester").insert()
		self.addCleanup(frappe.delete_doc, "User", user.name, force=True)

		original_userid = user.get_social_login_userid("frappe")
		self.assertTrue(original_userid)
		row_name = user.social_logins[0].name

		# the owner can be granted write on their own record, e.g. through sharing
		frappe.share.add("User", user.name, user.name, write=1)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(user.name)

		# a write cannot change the OIDC `sub`, even though `userid` is only read_only in the form
		user = frappe.get_doc("User", user.name)
		user.social_logins[0].userid = "Administrator"
		user.save()
		self.assertEqual(frappe.db.get_value("User Social Login", row_name, "userid"), original_userid)

		# nor can it be replaced by dropping the row and appending a crafted one
		user.social_logins = []
		user.set_social_login_userid("frappe", "Administrator")
		user.save()
		self.assertEqual(
			frappe.db.get_value("User Social Login", {"parent": user.name, "provider": "frappe"}, "userid"),
			original_userid,
		)

		# nor through a direct save of the child row, which skips the parent controller
		row_name = frappe.db.get_value(
			"User Social Login", {"parent": user.name, "provider": "frappe"}, "name"
		)
		child = frappe.get_doc("User Social Login", row_name)
		child.userid = "Administrator"
		self.assertRaises(frappe.ValidationError, child.save)
		self.assertEqual(frappe.db.get_value("User Social Login", row_name, "userid"), original_userid)

		# nor by relabeling the frappe row as another provider to smuggle a userid back in
		child = frappe.get_doc("User Social Login", row_name)
		child.provider = "custom"
		child.userid = "Administrator"
		self.assertRaises(frappe.ValidationError, child.save)
		self.assertEqual(frappe.db.get_value("User Social Login", row_name, "provider"), "frappe")

	def insert_user_as_manager(self, first_name, username=None):
		if frappe.session.user == "Administrator":
			manager = frappe.get_doc(
				doctype="User",
				email=f"{frappe.generate_hash()}@example.com",
				first_name="Manager",
				roles=[{"role": "System Manager"}],
			).insert()
			frappe.set_user(manager.name)

		return frappe.get_doc(
			doctype="User",
			email=f"{frappe.generate_hash()}@example.com",
			first_name=first_name,
			username=username,
		).insert()

	def test_username_from_a_taken_first_name(self):
		first_name = f"Tester {frappe.generate_hash(length=8)}"
		base = frappe.scrub(first_name)
		first = self.insert_user_as_manager(first_name)
		self.insert_user_as_manager("Decoy", username=f"{base}-\u00b2")
		second = self.insert_user_as_manager(first_name)

		self.assertEqual(first.username, base)
		self.assertEqual(second.username, f"{base}-1")

	def test_username_from_a_first_name_taken_with_accents(self):
		suffix = frappe.generate_hash(length=8)
		self.insert_user_as_manager("Accented", username=f"jos\u00e9{suffix}")
		self.insert_user_as_manager("Accented", username=f"jos\u00e9{suffix}-1")
		user = self.insert_user_as_manager(f"Jose{suffix}")

		self.assertTrue(user.username)

	def test_username_taken_while_the_user_is_saved(self):
		first_name = f"Tester {frappe.generate_hash(length=8)}"
		base = frappe.scrub(first_name)
		self.insert_user_as_manager(first_name)
		other = self.insert_user_as_manager("Other")
		validate_username = User.validate_username

		def taken_meanwhile(user):
			validate_username(user)
			frappe.db.set_value("User", other.name, "username", user.username)

		with patch.object(User, "validate_username", taken_meanwhile):
			second = self.insert_user_as_manager(first_name)

		self.assertEqual(second.username, f"{base}-2")
		self.assertFalse([m for m in frappe.message_log if "unique" in str(m)])

	def test_delete(self):
		frappe.get_doc("User", get_user_by_email("test@example.com")).add_roles("_Test Role 2")
		self.assertRaises(frappe.LinkExistsError, delete_doc, "Role", "_Test Role 2")
		frappe.db.delete("Has Role", {"role": "_Test Role 2"})
		delete_doc("Role", "_Test Role 2")

		if existing := get_user_by_email("_test@example.com"):
			delete_contact("_test@example.com")
			delete_doc("User", existing)

		user = frappe.copy_doc(self.globalTestRecords["User"][1])
		user.email = "_test@example.com"
		user.insert()

		frappe.get_doc({"doctype": "ToDo", "description": "_Test"}).insert()

		delete_contact("_test@example.com")
		delete_doc("User", user.name)

		self.assertTrue(not frappe.db.sql("""select * from `tabToDo` where allocated_to=%s""", (user.name,)))

		frappe.copy_doc(self.globalTestRecords["Role"][1]).insert()

	def test_get_value(self):
		user = get_user_by_email("test@example.com")
		self.assertEqual(frappe.db.get_value("User", user), user)
		self.assertEqual(frappe.db.get_value("User", {"email": "test@example.com"}), user)
		self.assertEqual(
			frappe.db.get_value("User", {"email": "test@example.com"}, "email"), "test@example.com"
		)
		self.assertEqual(
			frappe.db.get_value("User", {"email": "test@example.com"}, ["first_name", "email"]),
			("_Test", "test@example.com"),
		)
		self.assertEqual(
			frappe.db.get_value(
				"User", {"email": "test@example.com", "first_name": "_Test"}, ["first_name", "email"]
			),
			("_Test", "test@example.com"),
		)

		test_user = frappe.db.sql("select * from tabUser where name=%s", user, as_dict=True)[0]
		self.assertEqual(
			frappe.db.get_value("User", {"email": "test@example.com"}, "*", as_dict=True), test_user
		)

		self.assertEqual(frappe.db.get_value("User", "xxxtest@example.com"), None)

	def test_high_permlevel_validations(self):
		user = frappe.get_meta("User")
		self.assertTrue("roles" in [d.fieldname for d in user.get_high_permlevel_fields()])

		user = get_user_by_email("testperm@example.com")
		me = frappe.get_doc("User", user)
		me.remove_roles("System Manager")

		frappe.set_user("testperm@example.com")

		me = frappe.get_doc("User", user)
		me.add_roles("System Manager")

		# system manager is not added (it is reset)
		self.assertFalse("System Manager" in [d.role for d in me.roles])

		# ignore permlevel using flags
		me.flags.ignore_permlevel_for_fields = ["roles"]
		me.add_roles("System Manager")

		# system manager now added due to flags
		self.assertTrue("System Manager" in [d.role for d in me.get("roles")])

		# reset flags
		me.flags.ignore_permlevel_for_fields = None

		# change user
		frappe.set_user("Administrator")

		me = frappe.get_doc("User", user)
		me.add_roles("System Manager")

		# system manager now added by Administrator
		self.assertTrue("System Manager" in [d.role for d in me.get("roles")])

	def test_delete_user(self):
		new_user = frappe.get_doc(
			doctype="User", email="test-for-delete@example.com", first_name="Tester Delete User"
		).insert(ignore_if_duplicate=True)
		self.assertEqual(new_user.user_type, "Website User")

		# role with desk access
		new_user.add_roles("_Test Role 2")
		new_user.save()
		self.assertEqual(new_user.user_type, "System User")

		comm = frappe.get_doc(
			{
				"doctype": "Communication",
				"subject": "To check user able to delete even if linked with communication",
				"content": "To check user able to delete even if linked with communication",
				"sent_or_received": "Sent",
				"user": new_user.name,
			}
		)
		comm.insert(ignore_permissions=True)

		delete_contact(new_user.name)
		frappe.delete_doc("User", new_user.name)
		self.assertFalse(frappe.db.exists("User", new_user.name))

	def test_password_strength(self):
		# Test Password without Password Strength Policy
		with change_settings("System Settings", enable_password_policy=0):
			# password policy is disabled, test_password_strength should be ignored
			result = test_password_strength("test_password")
			self.assertFalse(result.get("feedback", None))

		# Test Password with Password Strenth Policy Set
		with change_settings("System Settings", enable_password_policy=1, minimum_password_score=1):
			# Score 0; should now fail
			result = test_password_strength("zxcvbn")
			self.assertEqual(result["feedback"]["password_policy_validation_passed"], False)
			self.assertRaises(
				frappe.exceptions.ValidationError, handle_password_test_fail, result["feedback"]
			)
			self.assertRaises(
				frappe.exceptions.ValidationError, handle_password_test_fail, result
			)  # test backwards compatibility

			# Score 1; should pass
			result = test_password_strength("bee2ve")
			self.assertEqual(result["feedback"]["password_policy_validation_passed"], True)

			# Score 4; should pass
			result = test_password_strength("Eastern_43A1W")
			self.assertEqual(result["feedback"]["password_policy_validation_passed"], True)

			result = test_password_strength("xK9#mP2$vL8@qR5&wN3*zB7!cF4^hJ6%tD1(gS0)yA9-eU2_iO5+kM8=nQ4~rV7")
			self.assertEqual(set(result), {"score", "feedback"})
			orjson_dumps(result)

			# test password strength while saving user with new password
			user = frappe.get_doc("User", get_user_by_email("test@example.com"))
			toggle_test_mode(False)
			try:
				user.new_password = "password"
				self.assertRaises(frappe.exceptions.ValidationError, user.save)
				user.reload()
				user.new_password = "Eastern_43A1W"
				user.save()
			finally:
				toggle_test_mode(True)

	def test_comment_mentions(self):
		comment = """
			<span class="mention" data-id="test.comment@example.com" data-value="Test" data-denotation-char="@">
				<span><span class="ql-mention-denotation-char">@</span>Test</span>
			</span>
		"""
		self.assertEqual(extract_mentions(comment)[0], "test.comment@example.com")

		comment = """
			<div>
				Testing comment,
				<span class="mention" data-id="test.comment@example.com" data-value="Test" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Test</span>
				</span>
				please check
			</div>
		"""
		self.assertEqual(extract_mentions(comment)[0], "test.comment@example.com")
		comment = """
			<div>
				Testing comment for
				<span class="mention" data-id="test_user@example.com" data-value="Test" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Test</span>
				</span>
				and
				<span class="mention" data-id="test.again@example1.com" data-value="Test" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Test</span>
				</span>
				please check
			</div>
		"""
		self.assertEqual(extract_mentions(comment)[0], "test_user@example.com")
		self.assertEqual(extract_mentions(comment)[1], "test.again@example1.com")

		frappe.delete_doc("User Group", "Team")
		doc = frappe.get_doc(
			{
				"doctype": "User Group",
				"name": "Team",
				"user_group_members": [
					{"user": get_user_by_email("test@example.com")},
					{"user": get_user_by_email("test1@example.com")},
				],
			}
		)

		doc.insert()

		comment = """
			<div>
				Testing comment for
				<span class="mention" data-id="Team" data-value="Team" data-is-group="true" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Team</span>
				</span> and
				<span class="mention" data-id="Unknown Team" data-value="Unknown Team" data-is-group="true"
				data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Unknown Team</span>
				</span><!-- this should be ignored-->
				please check
			</div>
		"""
		self.assertListEqual(
			extract_mentions(comment),
			[get_user_by_email("test@example.com"), get_user_by_email("test1@example.com")],
		)

	@requires_test_service(TestService.WEB_SERVER)
	@IntegrationTestCase.change_settings("System Settings", commit=True, password_reset_limit=1)
	def test_rate_limiting_for_reset_password(self):
		url = get_url()
		data = {"cmd": "frappe.core.doctype.user.user.reset_password", "user": "test@test.com"}

		# Password reset is limited by the request IP, not the submitted user.
		# Clear all identities for this endpoint instead of guessing the IP key.
		counter_prefix = f"rl:{data['cmd']}:"
		frappe.cache.delete_keys(counter_prefix)
		self.addCleanup(frappe.cache.delete_keys, counter_prefix)

		c = FrappeClient(url)
		res1 = c.session.post(url, data=data, verify=c.verify, headers=c.headers)
		res2 = c.session.post(url, data=data, verify=c.verify, headers=c.headers)
		self.assertEqual(res1.status_code, 200)
		self.assertEqual(res2.status_code, 429)

	def test_user_rename(self):
		old_name = "test_user_rename@example.com"
		new_name = "test_user_rename_new@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": old_name,
				"enabled": 1,
				"first_name": "_Test",
				"new_password": "Eastern_43A1W",
				"roles": [{"doctype": "Has Role", "parentfield": "roles", "role": "System Manager"}],
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

		frappe.rename_doc("User", user.name, new_name)
		self.assertTrue(frappe.db.exists("Notification Settings", new_name))

		frappe.delete_doc("User", new_name)

	def test_user_rename_defers_the_owner_sweep(self):
		new_name = "test_user_rename_owner_new@example.com"
		old_name = get_or_create_user("test_user_rename_owner@example.com")

		todo = frappe.get_doc({"doctype": "ToDo", "description": "owned by a renamed user"}).insert()
		frappe.db.set_value(
			"ToDo", todo.name, {"owner": old_name, "modified_by": old_name}, update_modified=False
		)

		with patch("frappe.enqueue") as enqueue:
			frappe.rename_doc("User", old_name, new_name)

		enqueue.assert_any_call(
			"frappe.core.doctype.user.user.rewrite_owner_fields",
			old_name=old_name,
			new_name=new_name,
			commit=True,
			queue="long",
			timeout=36000,
			enqueue_after_commit=True,
		)
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "owner"), old_name)

		rewrite_owner_fields(old_name, new_name)

		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "owner"), new_name)
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "modified_by"), new_name)

	def test_owner_sweep_leaves_rows_of_a_new_user_at_the_old_name(self):
		old_name = get_or_create_user("test_user_rename_reused@example.com")
		new_name = "test_user_rename_reused_new@example.com"
		taken_at = frappe.db.get_value("User", old_name, "creation")

		before = frappe.get_doc({"doctype": "ToDo", "description": "written before the rename"}).insert()
		after = frappe.get_doc({"doctype": "ToDo", "description": "written by the new holder"}).insert()
		for todo, written_at in (
			(before, add_to_date(taken_at, minutes=-1)),
			(after, add_to_date(taken_at, minutes=1)),
		):
			frappe.db.set_value(
				"ToDo",
				todo.name,
				{"owner": old_name, "modified_by": old_name, "creation": written_at, "modified": written_at},
				update_modified=False,
			)

		rewrite_owner_fields(old_name, new_name)

		self.assertEqual(
			frappe.db.get_value("ToDo", before.name, ["owner", "modified_by"]), (new_name, new_name)
		)
		self.assertEqual(
			frappe.db.get_value("ToDo", after.name, ["owner", "modified_by"]), (old_name, old_name)
		)

	def test_user_rename_and_delete_blocked_while_owner_sweep_is_pending(self):
		freed, renamed, other, unrelated = (
			get_or_create_user(email)
			for email in (
				"test_user_rename_pending_freed@example.com",
				"test_user_rename_pending@example.com",
				"test_user_rename_pending_other@example.com",
				"test_user_rename_pending_unrelated@example.com",
			)
		)

		def pending_job(method, old_name, new_name):
			return SimpleNamespace(
				kwargs={
					"site": frappe.local.site,
					"method": method,
					"kwargs": {"old_name": old_name, "new_name": new_name},
				}
			)

		pending_jobs = [
			pending_job("frappe.core.doctype.user.user.rewrite_owner_fields", freed, renamed),
			pending_job("frappe.utils.global_search.rebuild_for_doctype", unrelated, unrelated),
		]
		with (
			patch("frappe.core.doctype.user.user.get_queue", return_value=SimpleNamespace(jobs=pending_jobs)),
			patch("frappe.core.doctype.user.user.get_running_jobs_in_queue", return_value=[]),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "still being applied"):
				frappe.rename_doc("User", renamed, "test_user_rename_pending_new@example.com")

			with self.assertRaisesRegex(frappe.ValidationError, "still being applied"):
				frappe.rename_doc("User", other, renamed, merge=True)

			with self.assertRaisesRegex(frappe.ValidationError, "still being applied"):
				frappe.rename_doc("User", freed, "test_user_rename_pending_freed_new@example.com")

			with self.assertRaisesRegex(frappe.ValidationError, "still being applied"):
				frappe.delete_doc("User", freed)

			frappe.rename_doc("User", unrelated, "test_user_rename_pending_unrelated_new@example.com")

	def test_user_rename_updates_private_workspace(self):
		old_email = "test_user_rename_ws@example.com"
		new_name = "test_user_rename_ws_new@example.com"
		actor_email = "test_user_rename_ws_actor@example.com"

		for email in (old_email, new_name, actor_email):
			if user := get_user_by_email(email):
				frappe.delete_doc("User", user, ignore_permissions=True, force=True)

		old_name = (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": old_email,
					"enabled": 1,
					"first_name": "_Test",
					"new_password": "Eastern_43A1W",
					"roles": [{"doctype": "Has Role", "parentfield": "roles", "role": "System Manager"}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

		actor_name = (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": actor_email,
					"enabled": 1,
					"first_name": "_Test Actor",
					"new_password": "Eastern_43A1W",
					"roles": [{"doctype": "Has Role", "parentfield": "roles", "role": "System Manager"}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

		old_workspace = f"Test Rename Workspace-{old_name}"
		if frappe.db.exists("Workspace", old_workspace):
			frappe.delete_doc("Workspace", old_workspace, ignore_permissions=True, force=True)

		frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "Test Rename Workspace",
				"label": old_workspace,
				"type": "Workspace",
				"for_user": old_name,
				"public": 0,
				# Mandatory now: a private workspace belongs to a module like any other.
				"module": "Core",
				"content": "[]",
			}
		).insert(ignore_permissions=True)

		with self.set_user(actor_name):
			frappe.rename_doc("User", old_name, new_name)

		new_workspace = f"Test Rename Workspace-{new_name}"
		self.assertTrue(frappe.db.exists("Workspace", new_workspace))
		self.assertEqual(frappe.db.get_value("Workspace", new_workspace, "for_user"), new_name)

		frappe.delete_doc("Workspace", new_workspace, ignore_permissions=True, force=True)
		frappe.delete_doc("User", new_name, ignore_permissions=True, force=True)
		frappe.delete_doc("User", actor_name, ignore_permissions=True, force=True)

	def test_signup(self):
		import frappe.website.utils

		random_user = frappe.mock("email")
		random_user_name = frappe.mock("name")
		# disabled signup
		with patch.object(user_module, "is_signup_disabled", return_value=True):
			self.assertTupleEqual(
				sign_up(random_user, random_user_name, "/signup"),
				(0, "We could not create an account with the provided details."),
			)

		self.assertTupleEqual(
			sign_up(random_user, random_user_name, "/welcome"),
			(1, "Please check your email for verification"),
		)
		self.assertEqual(
			frappe.cache.hget("redirect_after_login", get_user_by_email(random_user)),
			sanitize_redirect("/welcome"),
		)

		# re-register
		self.assertTupleEqual(
			sign_up(random_user, random_user_name, "/welcome"),
			(0, "We could not create an account with the provided details."),
		)

		# disabled user
		user = frappe.get_doc("User", get_user_by_email(random_user))
		user.enabled = 0
		user.save()

		self.assertTupleEqual(
			sign_up(random_user, random_user_name, "/welcome"),
			(0, "We could not create an account with the provided details."),
		)

		# throttle user creation
		with patch.object(user_module.frappe.db, "get_creation_count", return_value=301):
			response = frappe.local.response
			frappe.local.response = frappe._dict()
			try:
				self.assertIsNone(sign_up(frappe.mock("email"), random_user_name, "/signup"))
				self.assertEqual(frappe.local.response["http_status_code"], 429)
			finally:
				frappe.local.response = response

	@IntegrationTestCase.change_settings("System Settings", password_reset_limit=6)
	def test_reset_password(self):
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		old_password = "Eastern_43A1W"
		new_password = "easy_password"

		set_request(path="/random")
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()
		# used by rate limiter when calling reset_password
		frappe.local.request_ip = "127.0.0.69"

		frappe.set_user("testpassword@example.com")
		test_user = frappe.get_doc("User", get_user_by_email("testpassword@example.com"))
		key = self.reset_password(test_user)
		self.assertEqual(update_password(new_password, key=key), "/desk")
		self.assertEqual(
			update_password(new_password, key="wrong_key"),
			"The reset password link has either been used before or is invalid",
		)

		# password verification should fail with old password
		self.assertRaises(frappe.exceptions.AuthenticationError, verify_password, old_password)
		verify_password(new_password)

		# reset password
		update_password(old_password, old_password=new_password)
		self.assertRaises(TypeError, update_password, "test", 1, ["like", "%"])

		password_strength_response = {
			"feedback": {"password_policy_validation_passed": False, "suggestions": ["Fix password"]}
		}

		# password strength failure test
		with patch.object(user_module, "test_password_strength", return_value=password_strength_response):
			self.assertRaisesRegex(
				frappe.exceptions.ValidationError,
				"Fix password",
				update_password,
				new_password,
				0,
				test_user.reset_password_key,
			)

		# test redirect URL for website users
		frappe.set_user("test2@example.com")
		self.assertEqual(update_password(new_password, old_password=old_password), "me")
		# reset password
		update_password(old_password, old_password=new_password)

		# test API endpoint
		with patch.object(user_module.frappe, "sendmail") as sendmail:
			from unittest.mock import MagicMock

			mock_q = MagicMock()
			mock_q.name = "test-email-queue-name"
			mock_q.message = "Subject: Test\n\nDear User, here is your link"
			sendmail.return_value = mock_q
			frappe.clear_messages()
			test_user = frappe.get_doc("User", get_user_by_email("test2@example.com"))
			self.assertEqual(reset_password(user="test2@example.com"), None)
			test_user.reload()
			link = sendmail.call_args_list[0].kwargs["args"]["link"]
			key = parse_qs(urlparse(link).query)["key"][0]
			self.assertEqual(update_password(new_password, key=key), "me")
			update_password(old_password, old_password=new_password)
			self.assertEqual(
				frappe.message_log[0].get("message"),
				"If this email is registered with us, we have sent password reset instructions to it. Please check your inbox.",
			)

		sendmail.assert_called_once()
		self.assertEqual(sendmail.call_args[1]["recipients"], "test2@example.com")

		# Constant-response guarantee: every path — existing user, Administrator,
		# and non-existent user — must return None AND enqueue the same generic
		# message, so callers cannot distinguish between them.
		_GENERIC_MSG = "If this email is registered with us, we have sent password reset instructions to it. Please check your inbox."

		frappe.clear_messages()
		self.assertIsNone(reset_password(user="test2@example.com"))
		self.assertEqual(frappe.message_log[0].get("message"), _GENERIC_MSG)

		frappe.clear_messages()
		self.assertIsNone(reset_password(user="Administrator"))
		self.assertEqual(frappe.message_log[0].get("message"), _GENERIC_MSG)

		frappe.clear_messages()
		self.assertIsNone(reset_password(user="random"))
		self.assertEqual(frappe.message_log[0].get("message"), _GENERIC_MSG)

	def test_change_password_sets_last_password_reset_date(self):
		user = get_user_by_email("testpassword@example.com")
		frappe.db.set_value("User", user, "last_password_reset_date", add_days(today(), -2))

		frappe.set_user(user)
		change_password(user, "Eastern_43A1W")

		self.assertEqual(frappe.db.get_value("User", user, "last_password_reset_date"), getdate())

	def test_user_onload_modules(self):
		"""The editor lists custom modules, and keeps a blocked module even after it is deleted"""
		from frappe.desk.form.load import getdoc

		for name in ("_Test Site Module", "_Test Gone Module"):
			frappe.get_doc({"doctype": "Module Def", "module_name": name, "custom": 1}).insert(
				ignore_if_duplicate=True
			)

		with test_user(roles=["System Manager"]) as admin, test_user(roles=["_Test Role 2"]) as user:
			user.append("block_modules", {"module": "_Test Gone Module"})
			user.save()
			frappe.delete_doc("Module Def", "_Test Gone Module", force=True)
			self.assertFalse(frappe.db.exists("Module Def", "_Test Gone Module"))

			with self.set_user(admin.name):
				frappe.response.docs = []
				getdoc("User", user.name)
				all_modules = frappe.response.docs[0].get("__onload").get("all_modules")

		self.assertIn("Core", all_modules)
		self.assertIn("_Test Site Module", all_modules)
		self.assertIn("_Test Gone Module", all_modules)

	def test_user_onload_modules_hidden_from_normal_user(self):
		from frappe.desk.form.load import getdoc

		with test_user(roles=["_Test Role 2"]) as user, self.set_user(user.name):
			frappe.response.docs = []
			getdoc("User", user.name)
			self.assertNotIn("all_modules", frappe.response.docs[0].get("__onload"))

	def test_default_app(self):
		from frappe.apps import get_default_path

		with test_user(roles=["System Manager"]) as user:
			user.default_app = "next_erp"
			user.save()
			self.assertFalse(user.default_app)

			frappe.set_user(user.name)
			user.db_set("default_app", "next_erp")
			user.reload()
			self.assertTrue(user.default_app)

			get_default_path()  # defaults will also trigger hooks logic

	def test_reset_password_finds_the_user_by_email(self):
		from frappe.core.doctype.user.user import reset_password

		frappe.local.request_ip = "127.0.0.71"
		admin_key = frappe.db.get_value("User", "Administrator", "reset_password_key")

		with test_user(roles=[], generated_id=True) as user, patch("frappe.sendmail"):
			reset_password(user.name)
			self.assertFalse(frappe.db.get_value("User", user.name, "reset_password_key"))

			reset_password(f" {user.email.upper()} ")
			self.assertTrue(frappe.db.get_value("User", user.name, "reset_password_key"))

			reset_password(frappe.db.get_value("User", "Administrator", "email"))
			self.assertEqual(frappe.db.get_value("User", "Administrator", "reset_password_key"), admin_key)

	@IntegrationTestCase.change_settings("System Settings", reset_password_link_expiry_duration=1)
	def test_reset_password_link_expiry(self):
		new_password = "new_password"
		frappe.set_user("testpassword@example.com")
		test_user = frappe.get_doc("User", get_user_by_email("testpassword@example.com"))
		key = self.reset_password(test_user)
		time.sleep(1)

		self.assertEqual(
			update_password(new_password, key=key),
			"The reset password link has been expired",
		)

	def test_update_password_needs_a_reset_key_or_old_password(self):
		for user in ("Guest", "testpassword@example.com"):
			frappe.set_user(user)
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Either a password reset key or old password is required",
				update_password,
				"Western_43A1W",
			)
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Either a password reset key or old password is required",
				update_password,
				"Western_43A1W",
				key="",
				old_password="",
			)

	@unimplemented_for(db_type_is.SQLITE)
	def test_reset_password_key_cannot_be_used_by_a_concurrent_request(self):
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		other = get_db(
			socket=frappe.db.socket,
			host=frappe.db.host,
			user=frappe.db.user,
			password=frappe.db.password,
			port=frappe.db.port,
			cur_db_name=frappe.db.cur_db_name,
		)
		self.addCleanup(other.close)

		with test_user(roles=[], commit=True) as user:
			key = self.reset_password(user)
			hashed_key = sha256_hash(key)
			# the second connection only sees committed rows
			frappe.db.commit()  # nosemgrep

			set_request(path="/random")
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()

			def competing_request(*args):
				# a second request with the same key can neither take it nor wait for it
				with patch.object(frappe.local, "db", other):
					with self.assertRaises(frappe.QueryTimeoutError):
						frappe.db.get_value(
							"User", {"reset_password_key": hashed_key}, for_update=True, wait=False
						)
					frappe.db.rollback()

				# clearing sessions commits mid-request; the key must already be gone by then
				frappe.db.commit()  # nosemgrep
				with patch.object(frappe.local, "db", other):
					self.assertFalse(frappe.db.exists("User", {"reset_password_key": hashed_key}))
					frappe.db.rollback()
				return False

			with patch.object(user_module, "is_password_reused", side_effect=competing_request) as probe:
				self.assertEqual(update_password("Eastern_43A1W", key=key), "me")
			probe.assert_called_once()
			frappe.set_user("Administrator")

	@contextmanager
	def outgoing_email_account(self):
		exists = frappe.db.exists

		def exists_with_outgoing_account(doctype, *args, **kwargs):
			if doctype == "Email Account":
				return "Test Outgoing Account"
			return exists(doctype, *args, **kwargs)

		with patch.object(frappe.db, "exists", side_effect=exists_with_outgoing_account):
			yield

	def test_second_save_of_new_user_does_not_send_password_changed_alert(self):
		"""Social login inserts the user through add_roles and saves it again in the same request."""
		frappe.set_user("Guest")
		user: User = frappe.new_doc(
			"User",
			email="oauth-signup@example.com",
			first_name="OAuth",
			user_type="Website User",
			new_password=frappe.generate_hash(),
		)
		user.flags.ignore_permissions = True
		user.flags.no_welcome_mail = True
		try:
			with self.outgoing_email_account(), patch.object(frappe, "sendmail") as sendmail:
				user.add_roles("_Test Role")
				user.save()

			sendmail.assert_not_called()
		finally:
			frappe.set_user("Administrator")
			user.delete(force=True, ignore_permissions=True)

	def test_password_change_by_user_still_sends_password_changed_alert(self):
		with test_user(roles=["_Test Role"]) as created:
			frappe.set_user(created.name)
			user: User = frappe.get_doc("User", created.name)
			user.new_password = "Eastern_43A1W_changed"
			with self.outgoing_email_account(), patch.object(frappe, "sendmail") as sendmail:
				user.save()

			sendmail.assert_called_once()
			self.assertEqual(sendmail.call_args.kwargs["recipients"], [created.email])
			frappe.set_user("Administrator")

	def test_bulk_add_roles(self):
		"""Roles are appended across the selection without disturbing existing ones."""
		with (
			test_user(roles=["_Test Role"]) as first,
			test_user(roles=["Website Manager"]) as second,
		):
			bulk_add_roles([first.name, second.name], ["_Test Role 4", "_Test Role"])

			first.reload()
			second.reload()

			self.assertCountEqual([d.role for d in first.roles], ["_Test Role", "_Test Role 4"])
			self.assertCountEqual(
				[d.role for d in second.roles], ["Website Manager", "_Test Role 4", "_Test Role"]
			)

	def test_bulk_remove_roles(self):
		"""Roles are stripped across the selection, leaving other roles intact."""
		with (
			test_user(roles=["_Test Role", "Website Manager"]) as first,
			test_user(roles=["_Test Role"]) as second,
		):
			bulk_remove_roles([first.name, second.name], ["_Test Role", "_Test Role 4"])

			first.reload()
			second.reload()

			self.assertCountEqual([d.role for d in first.roles], ["Website Manager"])
			self.assertCountEqual([d.role for d in second.roles], [])

			bulk_remove_roles([], ["Website Manager"])
			bulk_remove_roles([first.name], [])

			first.reload()
			self.assertCountEqual([d.role for d in first.roles], ["Website Manager"])

	def test_bulk_role_endpoints_enqueue_large_batches(self):
		"""Over 20 users, each endpoint defers to its own background job."""
		users = [f"bulk{i}@example.com" for i in range(21)]

		with patch.object(frappe, "enqueue") as mocked_enqueue:
			bulk_add_roles(users, ["Blogger"])

		mocked_enqueue.assert_called_once()
		self.assertEqual(mocked_enqueue.call_args.args[0], "frappe.core.doctype.user.user._assign_roles")

		with patch.object(frappe, "enqueue") as mocked_enqueue:
			bulk_remove_roles(users, ["Blogger"])

		mocked_enqueue.assert_called_once()
		self.assertEqual(mocked_enqueue.call_args.args[0], "frappe.core.doctype.user.user._unassign_roles")

	def test_bulk_role_args_are_validated(self):
		"""Parsed arguments must be lists of plain strings, within the batch cap."""
		with self.assertRaises(frappe.ValidationError):
			bulk_add_roles([{"name": ["!=", ""]}], ["Blogger"])

		with self.assertRaises(frappe.ValidationError):
			bulk_add_roles(["someone@example.com"], [{"role": ["!=", ""]}])

		with self.assertRaises(frappe.ValidationError):
			bulk_add_roles([f"u{i}@example.com" for i in range(501)], ["Blogger"])

		with self.assertRaises(frappe.ValidationError):
			bulk_remove_roles([f"u{i}@example.com" for i in range(501)], ["Blogger"])

	def test_bulk_role_endpoints_require_write_permission(self):
		with test_user(roles=["_Test Role 4"]) as actor, test_user(roles=["_Test Role 4"]) as target:
			with self.set_user(actor.name):
				with self.assertRaises(frappe.PermissionError):
					bulk_add_roles([target.name], ["Website Manager"])

				with self.assertRaises(frappe.PermissionError):
					bulk_remove_roles([target.name], ["_Test Role 4"])


class TestImpersonation(FrappeAPITestCase):
	def test_impersonation(self):
		with test_user(roles=["System Manager"], commit=True) as user:
			response = self.post(
				self.method("frappe.core.doctype.user.user.impersonate"),
				{"user": user.name, "reason": "test", "sid": self.sid},
			)
			self.assertEqual(response.status_code, 200)
			resp = self.get(self.method("frappe.auth.get_logged_user"))
			self.assertEqual(resp.json["message"], user.name)


class TestUserEmailHelpers(IntegrationTestCase):
	def test_get_email_addresses(self):
		with test_user(roles=[], generated_id=True) as user:
			self.assertEqual(
				get_email_addresses([user.name, "Guest", "guest", "_Test Missing User", None]), {user.email}
			)

	def test_users_cant_take_invalid_domain_emails(self):
		toggle_test_mode(False)
		self.addCleanup(toggle_test_mode, True)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(doctype="User", email="admin@frappe.invalid", first_name="Reserved").insert()

		with test_user(roles=[], generated_id=True) as user:
			frappe.db.set_value("User", user.name, "email", f"{user.name}@frappe.invalid")
			user = frappe.get_doc("User", user.name)
			user.flags.skip_email_from_name = True
			user.first_name = "Renamed"
			user.save()

			user.email = f"{user.name}-new@frappe.invalid"
			with self.assertRaises(frappe.ValidationError):
				user.save()

		with test_user(roles=[]) as user, self.assertRaises(frappe.ValidationError):
			frappe.rename_doc("User", user.name, f"{user.name}.invalid")

	def test_email_patch_moves_administrators_email_off_a_users_id(self):
		from frappe.patches.v16_0.set_user_email_from_name import execute

		frappe.db.savepoint("email_patch")
		self.addCleanup(frappe.db.rollback, save_point="email_patch")

		def add_user_named(name):
			user = frappe.new_doc("User", email=f"_test_{frappe.generate_hash(length=6)}@example.com")
			user.first_name = "Clash"
			user.flags.skip_email_from_name = True
			user.insert(set_name=name)

		# a changed email is left alone: migrate stops
		frappe.db.set_value("User", "Administrator", "email", "_test_owner@example.com")
		add_user_named("_test_owner@example.com")
		self.assertRaises(frappe.ValidationError, execute)
		frappe.db.set_value("User", "Administrator", "email", "admin@example.com")
		frappe.delete_doc("User", "_test_owner@example.com", force=True, ignore_permissions=True)

		add_user_named("admin@example.com")
		execute()
		self.assertEqual(frappe.db.get_value("User", "Administrator", "email"), "admin@frappe.invalid")
		self.assertEqual(frappe.db.get_value("User", "admin@example.com", "email"), "admin@example.com")

	def test_users_are_found_by_email(self):
		from frappe.core.doctype.user.user import user_query

		with (
			test_user(roles=["Desk User"]) as searcher,
			test_user(roles=["Desk User"], generated_id=True, email="_test_find_me@example.com") as user,
			self.set_user(searcher.name),
		):
			found = user_query("User", "_test_find_me", "name", 0, 20, {})
			self.assertIn(user.name, [row[0] for row in found])

	def test_set_user_takes_an_email(self):
		with test_user(roles=[], generated_id=True) as user:
			with self.set_user(f" {user.email.upper()} "):
				self.assertEqual(frappe.session.user, user.name)

			with self.set_user(user.name):
				self.assertEqual(frappe.session.user, user.name)

		with self.set_user("_test_no_such_user@example.com"):
			self.assertEqual(frappe.session.user, "_test_no_such_user@example.com")

	def test_existing_contact_is_updated_despite_missing_mandatory_fields(self):
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		email = "_test_contact_mandatory@example.com"
		contact = frappe.new_doc("Contact", first_name="Old")
		contact.add_email(email, is_primary=True)
		contact.insert()

		property_setter = make_property_setter("Contact", "company_name", "reqd", 1, "Check")
		self.addCleanup(frappe.clear_cache, doctype="Contact")
		self.addCleanup(frappe.delete_doc, "Property Setter", property_setter.name, force=True)

		user = frappe.new_doc("User", email=email, first_name="New")
		user.insert()
		self.addCleanup(frappe.delete_doc, "User", user.name, force=True)

		self.assertEqual(frappe.db.get_value("Contact", contact.name, "first_name"), "New")

	def test_get_user_by_email(self):
		with test_user(roles=[], generated_id=True) as user:
			self.assertEqual(get_user_by_email(f" {user.email.upper()} "), user.name)

		admin_email = frappe.db.get_value("User", "Administrator", "email")
		self.assertIsNone(get_user_by_email(admin_email))
		self.assertEqual(get_user_by_email(admin_email, include_standard_users=True), "Administrator")

	def test_get_user_display_id(self):
		with test_user(roles=[], generated_id=True) as user:
			self.assertEqual(get_user_display_id(user.name), user.email)

		self.assertEqual(get_user_display_id("Administrator"), "Administrator")
		self.assertEqual(get_user_display_id("_Test Missing User"), "_Test Missing User")

	def test_get_system_managers(self):
		from frappe.email import get_system_managers as get_system_manager_emails
		from frappe.utils.user import get_system_managers

		with test_user(roles=["System Manager"], generated_id=True) as user:
			self.assertIn(user.email, get_system_manager_emails())
			self.assertTrue(any(user.email in manager for manager in get_system_managers()))

	def test_contact_follows_a_changed_email(self):
		from frappe.contacts.doctype.address.address import get_user_contacts

		with test_user(roles=[], generated_id=True) as user:
			old_email = user.email
			contact = frappe.get_doc("Contact", {"user": user.name})
			frappe.db.set_value("User", user.name, "email", f"changed_{old_email}")
			user.reload()
			create_contact(user, old_email=old_email)

			self.assertEqual(
				frappe.get_all("Contact", filters={"user": user.name}, pluck="name"), [contact.name]
			)
			emails = frappe.get_doc("Contact", contact.name).email_ids
			self.assertEqual({row.email_id: row.is_primary for row in emails}, {old_email: 0, user.email: 1})
			self.assertEqual(get_user_contacts(user.name), [contact.name])

	def test_contact_keeps_a_primary_other_than_the_users_email(self):
		with test_user(roles=[], generated_id=True) as user:
			old_email = user.email
			contact = frappe.get_doc("Contact", {"user": user.name})
			contact.add_email("_test_billing@example.com")
			for row in contact.email_ids:
				row.is_primary = row.email_id == "_test_billing@example.com"
			contact.save()

			create_contact(user)
			self.assertEqual(
				frappe.db.get_value("Contact", contact.name, "email_id"), "_test_billing@example.com"
			)

			frappe.db.set_value("User", user.name, "email", f"changed_{old_email}")
			user.reload()
			create_contact(user, old_email=old_email)

			emails = frappe.get_doc("Contact", contact.name).email_ids
			self.assertEqual(
				{row.email_id: row.is_primary for row in emails},
				{"_test_billing@example.com": 1, old_email: 0, user.email: 0},
			)

	def test_contact_of_another_user_is_left_alone(self):
		with test_user(roles=[]) as owner, test_user(roles=[]) as user:
			contact = frappe.get_doc("Contact", {"user": owner.name})
			contact.add_email(user.email, autosave=True)
			frappe.db.delete("Contact", {"user": user.name})

			create_contact(user)

			contact.reload()
			self.assertEqual(contact.first_name, owner.first_name)
			self.assertEqual(contact.user, owner.name)
			self.assertEqual(
				frappe.db.get_value("Contact", {"user": user.name}, "first_name"), user.first_name
			)

	def test_contact_planted_with_a_users_email_is_not_taken_over(self):
		with test_user(roles=[]) as planter, test_user(roles=[], generated_id=True) as user:
			with self.set_user(planter.name):
				planted = frappe.get_doc(
					doctype="Contact",
					first_name="_Test Planted",
					email_ids=[{"email_id": user.email, "is_primary": 1}],
				).insert()
			self.assertFalse(planted.user)

			frappe.db.delete("Contact", {"user": user.name})
			create_contact(user)

			planted.reload()
			self.assertEqual((planted.first_name, planted.user), ("_Test Planted", None))
			self.assertTrue(frappe.db.exists("Contact", {"user": user.name}))

	def test_contact_with_the_users_email_as_secondary_is_reused(self):
		with test_user(roles=[], generated_id=True) as user:
			frappe.db.delete("Contact", {"user": user.name})
			contact = frappe.get_doc(
				doctype="Contact",
				first_name="_Test Secondary",
				email_ids=[
					{"email_id": "_test_work@example.com", "is_primary": 1},
					{"email_id": user.email},
				],
			).insert()
			self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

			create_contact(user)

			contact.reload()
			self.assertEqual((contact.user, contact.email_id), (user.name, "_test_work@example.com"))

	def test_only_user_managers_link_a_contact_to_a_user(self):
		with test_user(roles=[]) as planter, test_user(roles=[], generated_id=True) as user:
			with self.set_user(planter.name):
				address = frappe.get_doc(
					doctype="Address",
					address_title="_Test Planter",
					address_line1="1",
					city="Mumbai",
					country="India",
				).insert()
				contact = frappe.get_doc(doctype="Contact", first_name="_Test Linked", address=address.name)
				contact.user = user.name
				self.assertRaises(frappe.PermissionError, contact.insert)

	def test_contact_created_for_a_user_is_owned_by_administrator(self):
		with test_user(roles=[]) as creator:
			with self.set_user(creator.name):
				user = frappe.new_doc("User", email="_test_contact_owned@example.com", first_name="Owned")
				user.insert(ignore_permissions=True)
			self.addCleanup(frappe.delete_doc, "User", user.name, force=True)
			contact = frappe.db.get_value("Contact", {"user": user.name}, ["name", "owner"], as_dict=True)
			self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

			create_contact(user)

			self.assertEqual(contact.owner, "Administrator")
			self.assertEqual(
				frappe.get_all("Contact", filters={"user": user.name}, pluck="name"), [contact.name]
			)

	def test_contact_follows_a_renamed_user(self):
		old_name = "_test_contact_rename@example.com"
		new_name = "_test_contact_renamed@example.com"
		user = frappe.new_doc("User", email=old_name, first_name="Renamed")
		user.insert()
		self.addCleanup(frappe.delete_doc, "User", new_name, force=True)
		contact = frappe.db.get_value("Contact", {"user": old_name})
		frappe.db.set_value("Contact", contact, "owner", old_name)

		frappe.rename_doc("User", old_name, new_name, force=True)

		self.assertEqual(frappe.get_all("Contact", filters={"user": new_name}, pluck="name"), [contact])
		self.assertEqual(frappe.db.get_value("Contact", contact, "email_id"), new_name)


@contextmanager
def test_user(
	*,
	first_name: str | None = None,
	email: str | None = None,
	roles: list[str],
	commit=False,
	generated_id=False,
	**kwargs,
):
	"""Create a user for the duration of the test.

	`generated_id` gives the user a random ID instead of their email. Saving a freshly loaded copy
	of such a user fails: validation copies the ID into the email.
	"""
	try:
		first_name = first_name or frappe.generate_hash()
		email = email or (first_name + "@example.com")
		user: User = frappe.new_doc(
			"User",
			send_welcome_email=0,
			email=email,
			first_name=first_name,
			**kwargs,
		)
		user.append_roles(*roles)
		user.flags.skip_email_from_name = generated_id
		user.insert(set_name=frappe.generate_hash(length=10) if generated_id else None)
		yield user
		commit and frappe.db.commit()
	finally:
		user.delete(force=True, ignore_permissions=True)
		commit and frappe.db.commit()


def get_or_create_user(email: str) -> str:
	if user := get_user_by_email(email):
		return user

	new_user = frappe.new_doc("User", email=email, first_name="_Test", send_welcome_email=0)
	return new_user.insert(ignore_permissions=True).name


def delete_contact(user):
	frappe.db.delete("Contact", {"email_id": user})
	frappe.db.delete("Contact Email", {"email_id": user})


class TestNeedsPasswordSetup(IntegrationTestCase):
	def setUp(self):
		self.user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "site-owner@example.com",
				"first_name": "Site Owner",
				"send_welcome_email": 0,
			}
		).insert(ignore_if_duplicate=True)
		frappe.db.delete("__Auth", {"doctype": "User", "name": self.user.name})
		self.addCleanup(frappe.delete_doc, "User", self.user.name, force=True)

	def test_user_without_a_password_needs_one(self):
		self.assertTrue(needs_password_setup(self.user.name))

	def test_user_with_a_password_does_not(self):
		from frappe.utils.password import update_password as set_password

		set_password(self.user.name, "Eastern_43A1W")
		self.assertFalse(needs_password_setup(self.user.name))

	def test_a_token_request_cannot_set_the_first_password(self):
		from frappe.utils import set_request

		had_request = hasattr(frappe.local, "request")
		set_request(path="/api/method/ping", headers={"Authorization": "token key:secret"})
		frappe.local.request_ip = "127.0.0.1"
		frappe.set_user(self.user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				set_first_password("Eastern_43A1W")
		finally:
			frappe.set_user("Administrator")
			if not had_request:
				del frappe.local.request
		self.assertTrue(needs_password_setup(self.user.name))

	def test_sets_a_first_password_from_the_app(self):
		from frappe.utils.password import check_password

		frappe.set_user(self.user.name)
		try:
			set_first_password("Eastern_43A1W")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(check_password(self.user.name, "Eastern_43A1W"), self.user.name)
		self.assertFalse(needs_password_setup(self.user.name))

	def test_an_empty_first_password_is_refused(self):
		frappe.set_user(self.user.name)
		try:
			for empty in ("", "   "):
				with self.assertRaises(frappe.ValidationError):
					set_first_password(empty)
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(needs_password_setup(self.user.name))

	def test_a_first_password_spends_any_reset_link(self):
		self.user.reload()
		self.user._reset_password()
		self.assertTrue(frappe.db.get_value("User", self.user.name, "reset_password_key"))

		frappe.set_user(self.user.name)
		try:
			set_first_password("Eastern_43A1W")
		finally:
			frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("User", self.user.name, "reset_password_key"))
		self.assertEqual(
			str(frappe.db.get_value("User", self.user.name, "last_password_reset_date")), today()
		)

	def test_a_user_with_a_password_cannot_use_the_first_password_route(self):
		from frappe.utils.password import update_password as set_password

		set_password(self.user.name, "Eastern_43A1W")
		frappe.set_user(self.user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				set_first_password("Another_43A1W")
		finally:
			frappe.set_user("Administrator")

	@IntegrationTestCase.change_settings(
		"System Settings", enable_password_policy=1, minimum_password_score=2
	)
	def test_a_weak_first_password_is_refused(self):
		frappe.set_user(self.user.name)
		try:
			with self.assertRaises(frappe.ValidationError):
				set_first_password("aaaa")
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(needs_password_setup(self.user.name))

	def test_standard_users_never_do(self):
		self.assertFalse(needs_password_setup("Administrator"))
		self.assertFalse(needs_password_setup("Guest"))

	@IntegrationTestCase.change_settings("System Settings", login_with_email_link=1)
	def test_also_when_email_login_links_are_on(self):
		self.assertTrue(needs_password_setup(self.user.name))

	def test_also_on_frappe_cloud_v2(self):
		with patch.dict(
			frappe.conf, {"pilot_endpoint": "https://pilot.example.com", "pilot_auth_token": "t"}
		):
			self.assertTrue(needs_password_setup(self.user.name))

	@IntegrationTestCase.change_settings("System Settings", disable_user_pass_login=1)
	def test_not_when_password_login_is_off(self):
		self.assertFalse(needs_password_setup(self.user.name))

	def test_not_for_social_login_users(self):
		self.user.append("social_logins", {"provider": "google", "userid": "1234"})
		self.user.save()
		self.assertFalse(needs_password_setup(self.user.name))
