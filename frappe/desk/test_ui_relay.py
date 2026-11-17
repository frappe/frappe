from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.desk import ui_relay
from frappe.tests import IntegrationTestCase

USER = "test@example.com"
OTHER = "test2@example.com"


class FakeTabs:
	"""Stands in for the open tabs: each `publish_realtime` is answered through `reply`, as a tab does."""

	def __init__(self, tabs: dict[str, dict], parked: bool = False):
		self.tabs = tabs
		self.parked = parked
		self.calls: list[dict] = []

	def publish(self, event, message, user=None, **kwargs):
		if message["op"] == "tabs":
			for tab, info in self.tabs.items():
				ui_relay.reply(message["call_id"], {"tab": tab, "route": "/", "title": tab, **info}, tab=tab)
			return
		self.calls.append(message)
		if message["tab"] not in self.tabs:
			return
		tab = message["tab"]
		result = {"ok": True, "data": message["op"], "route": f"/{tab}", "dialogs": []}
		if self.parked:
			waiting = {"code": "waiting_for_user", "message": "Ask", "call": 3}
			ui_relay.reply(
				message["call_id"], {"ok": False, "error": waiting, "route": "/", "dialogs": []}, tab, False
			)
		ui_relay.reply(message["call_id"], result, tab=tab, final=True)


class TestUIRelay(IntegrationTestCase):
	def setUp(self):
		for user in (USER, OTHER):
			frappe.db.set_value("User", user, "agent_ui_relay", 1)
			frappe.clear_cache(user=user)
		frappe.set_user(USER)

	def tearDown(self):
		frappe.set_user("Administrator")

	def relay(self, tabs, **kwargs):
		fake = FakeTabs(tabs, **kwargs)
		return fake, patch("frappe.publish_realtime", side_effect=fake.publish)

	def test_refused_while_the_setting_is_off(self):
		frappe.db.set_value("User", USER, "agent_ui_relay", 0)
		frappe.clear_cache(user=USER)
		self.assertRaises(frappe.PermissionError, ui_relay.tabs)
		self.assertRaises(frappe.PermissionError, ui_relay.call, "state")

	def test_tabs_lists_the_last_focused_first(self):
		_, publish = self.relay({"a": {"focused_at": 1}, "b": {"focused_at": 5}})
		with publish:
			found = ui_relay.tabs()
		self.assertEqual([tab["tab"] for tab in found], ["b", "a"])

	def test_a_call_with_no_tab_goes_to_the_last_focused_one(self):
		fake, publish = self.relay({"a": {"focused_at": 1}, "b": {"focused_at": 5}})
		with publish:
			result = ui_relay.call("state")
		self.assertEqual((result["ok"], result["tab"], result["route"]), (True, "b", "/b"))
		self.assertEqual(fake.calls[0]["tab"], "b")

	def test_a_named_tab_gets_the_call_and_its_arguments(self):
		fake, publish = self.relay({"a": {"focused_at": 1}, "b": {"focused_at": 5}})
		with publish:
			result = ui_relay.call("run", tab="a", act="record.save", args={"x": 1})
		self.assertEqual(result["tab"], "a")
		self.assertEqual(
			(fake.calls[0]["act"], fake.calls[0]["args"], fake.calls[0]["op"]),
			("record.save", {"x": 1}, "run"),
		)

	def test_the_call_names_the_oauth_client_by_its_app_name_not_its_id(self):
		fake, publish = self.relay({"a": {"focused_at": 1}})
		with publish, patch("frappe.desk.ui_relay.get_oauth_client_name", return_value="frappectl"):
			ui_relay.call("state", tab="a")
		self.assertEqual(fake.calls[0]["client"], "frappectl")

	def test_a_call_without_an_oauth_client_names_none(self):
		fake, publish = self.relay({"a": {"focused_at": 1}})
		with publish:
			ui_relay.call("state", tab="a")
		self.assertIsNone(fake.calls[0]["client"])

	def test_a_gone_tab_is_not_found(self):
		fake, publish = self.relay({"a": {"focused_at": 1}})
		with publish, patch.object(ui_relay, "TAB_WAIT", 0.2):
			result = ui_relay.call("state", tab="gone")
		self.assertEqual(result["error"]["code"], "tab_not_found")
		self.assertFalse(fake.calls)

	def test_a_waiting_call_keeps_its_final_result_for_wait(self):
		_, publish = self.relay({"a": {"focused_at": 1}}, parked=True)
		with publish:
			waiting = ui_relay.call("run", act="record.submit")
			call_id = waiting["error"]["call"]
			ended = ui_relay.call("wait", call_id=call_id)
			again = ui_relay.call("wait", call_id=call_id)
		self.assertEqual(waiting["error"]["code"], "waiting_for_user")
		self.assertNotEqual(call_id, 3)
		self.assertTrue(ended["ok"] and again["ok"])
		kept = frappe.cache.make_key(f"user:{USER}:ui_reply:{call_id}")
		self.assertTrue(0 < frappe.cache.ttl(kept) <= ui_relay.KEEP)

	def test_a_silent_tab_gives_waiting_for_user_with_the_call_id(self):
		silent = FakeTabs({"a": {"focused_at": 1}})

		def publish(event, message, user=None, **kwargs):
			if message["op"] == "tabs":
				silent.publish(event, message, user)

		with patch("frappe.publish_realtime", side_effect=publish), patch.object(ui_relay, "CALL_WAIT", 0.3):
			result = ui_relay.call("state")
		self.assertEqual(result["error"]["code"], "waiting_for_user")
		self.assertTrue(result["error"]["call"])

	def test_another_user_cannot_answer_or_read_a_call(self):
		_, publish = self.relay({"a": {"focused_at": 1}}, parked=True)
		with publish:
			call_id = ui_relay.call("run", act="record.submit")["error"]["call"]
			frappe.set_user(OTHER)
			ui_relay.reply(call_id, {"ok": True, "data": "forged"}, tab="a", final=True)
			frappe.set_user(USER)
			ended = ui_relay.call("wait", call_id=call_id)
		self.assertEqual(ended["data"], "run")

	def test_a_call_rejects_an_unknown_op(self):
		self.assertRaises(frappe.ValidationError, ui_relay.call, "drop_database")

	def test_only_the_user_turns_the_setting_on(self):
		frappe.db.set_value("User", OTHER, "agent_ui_relay", 0)
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", OTHER)
		user.agent_ui_relay = 1
		self.assertRaises(frappe.PermissionError, user.save)
		user = frappe.get_doc("User", OTHER)
		user.agent_ui_relay = 0
		user.save()

	def test_a_token_request_cannot_turn_the_setting_on(self):
		frappe.db.set_value("User", USER, "agent_ui_relay", 0)
		user = frappe.get_doc("User", USER)
		user.agent_ui_relay = 1
		with patch.object(frappe, "request", SimpleNamespace(headers={"Authorization": "token k:s"})):
			self.assertRaises(frappe.PermissionError, user.save)

	def test_a_reply_needs_the_setting_and_stays_small(self):
		call_id = "a" * 20
		self.assertRaises(frappe.ValidationError, ui_relay.reply, call_id, {"blob": "x" * 1_000_001})
		for _ in range(ui_relay.MAX_REPLIES):
			ui_relay.reply(call_id, {"ok": True})
		self.assertRaises(frappe.ValidationError, ui_relay.reply, call_id, {"ok": True})
		frappe.db.set_value("User", USER, "agent_ui_relay", 0)
		frappe.clear_cache(user=USER)
		self.assertRaises(frappe.PermissionError, ui_relay.reply, "b" * 20, {"ok": True})

	def test_a_bad_answer_to_a_hello_is_skipped(self):
		fake = FakeTabs({"a": {"focused_at": 1}})

		def publish(event, message, user=None, **kwargs):
			if message["op"] == "tabs":
				ui_relay.reply(message["call_id"], {"route": "/"})  # no tab name, read first
			fake.publish(event, message, user)

		with patch("frappe.publish_realtime", side_effect=publish):
			self.assertEqual([item["tab"] for item in ui_relay.tabs()], ["a"])
			self.assertEqual(ui_relay.call("state", tab="a")["tab"], "a")

	def test_the_setting_is_in_the_shell_boot(self):
		from frappe.shell.boot import core_boot

		self.assertIs(core_boot()["agent_ui_relay"], True)
