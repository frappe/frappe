from unittest.mock import patch

import frappe
from frappe.storage.tests import hook_value
from frappe.tests.test_api import FrappeAPITestCase, make_request
from frappe.tests.utils import whitelist_for_tests

METHOD = "frappe.tests.test_streaming_request_paths.inspect_request_body"
ENDPOINT = f"/api/method/{METHOD}"


@whitelist_for_tests(allow_guest=True)
def inspect_request_body(offset: int | None = None, payload: str | None = None):
	request = frappe.request
	state = {
		"offset": offset,
		"payload": payload,
		"data_cached": hasattr(request, "_cached_data"),
		"form_cached": "form" in request.__dict__,
		"max_content_length": request.max_content_length,
		"user": frappe.session.user,
	}
	state["body"] = request.stream.read().decode()
	return state


class TestStreamingRequestPaths(FrappeAPITestCase):
	def request(self, path: str, streaming_paths: list[str], method="PUT", max_file_size=8, **kwargs):
		"""Send one request under the given body cap and streaming paths."""
		if "json" not in kwargs:
			kwargs["content_type"] = "application/octet-stream"
		configured = frappe._dict({**frappe.get_site_config(), "max_file_size": max_file_size})
		with (
			patch("frappe.config.get_site_config", return_value=configured),
			hook_value("streaming_request_paths", streaming_paths),
		):
			return make_request(
				target=self.TEST_CLIENT.open, args=(path,), kwargs={"method": method, **kwargs}
			)

	def state(self, response) -> dict:
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		# v2 returns the value under "data", v1 under "message"
		return response.json.get("data") or response.json["message"]

	def test_each_listed_api_mount_streams_the_body_past_the_cap(self):
		mounts = ("/api/method", "/api/v1/method", "/api/v2/method")
		listed = [f"{mount}/{METHOD}" for mount in mounts]
		for mount in mounts:
			with self.subTest(mount=mount):
				# query arguments still reach the handler; the body stays unread
				response = self.request(
					f"{mount}/{METHOD}?offset=17&_=cachebuster", listed, data=b"123456789"
				)
				state = self.state(response)
				self.assertEqual(state["offset"], 17)
				self.assertEqual(
					(state["data_cached"], state["form_cached"], state["max_content_length"], state["body"]),
					(False, False, None, "123456789"),
				)

	def test_unlisted_paths_keep_buffering_and_the_cap(self):
		for path, listed in (
			# only the unversioned mount is listed
			(f"/api/v2/method/{METHOD}", [ENDPOINT]),
			# a listed prefix does not match a sibling route
			(ENDPOINT, [ENDPOINT.removesuffix("_request_body")]),
			(ENDPOINT, ["/elsewhere/"]),
		):
			with self.subTest(path=path, listed=listed):
				state = self.state(self.request(path, listed, data=b"buffer"))
				self.assertEqual(
					(state["data_cached"], state["form_cached"], state["max_content_length"], state["body"]),
					(True, True, 8, "buffer"),
				)
				self.assertEqual(self.request(path, listed, data=b"123456789").status_code, 413)

	def test_listed_post_keeps_json_parsing_and_the_cap(self):
		response = self.request(
			ENDPOINT, [ENDPOINT], method="POST", max_file_size=1024, json={"payload": "finish"}
		)
		state = self.state(response)
		self.assertEqual(
			(state["payload"], state["data_cached"], state["max_content_length"]), ("finish", True, 1024)
		)

	def test_bearer_auth_leaves_the_streaming_body_unread(self):
		from frappe.integrations.doctype.oauth_bearer_token.test_oauth_bearer_token import (
			make_oauth_client,
		)

		user = "test1@example.com"
		access_token = frappe.generate_hash()
		client = make_oauth_client()
		token = frappe.get_doc(
			{
				"doctype": "OAuth Bearer Token",
				"client": client.name,
				"user": user,
				"access_token": access_token,
				"expires_in": 3600,
				"scopes": "all openid",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		# the request opens its own connection, so the token must be committed
		frappe.db.commit()  # nosemgrep
		self.addCleanup(frappe.db.commit)
		self.addCleanup(frappe.delete_doc, "OAuth Client", client.name, force=1, ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "OAuth Bearer Token", token.name, force=1, ignore_permissions=True)

		response = self.request(
			ENDPOINT,
			[ENDPOINT],
			data=b"123456789",
			headers={"Authorization": f"Bearer {access_token}"},
		)
		state = self.state(response)
		self.assertEqual((state["user"], state["data_cached"], state["body"]), (user, False, "123456789"))

	def test_upload_file_size_cap_applies_on_every_api_mount(self):
		for path in ("/api/method/upload_file", "/api/v1/method/upload_file", "/api/v2/method/upload_file"):
			with self.subTest(path=path), patch("frappe.core.api.file.get_max_file_size", return_value=8):
				response = make_request(
					target=self.TEST_CLIENT.post,
					args=(path,),
					kwargs={"data": {"filedata": "x" * 64, "filename": "big.txt"}},
				)
				self.assertEqual(response.status_code, 413, response.get_data(as_text=True)[:200])
