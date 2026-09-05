from unittest.mock import patch

from werkzeug.test import TestResponse

import frappe
from frappe.tests.test_api import FrappeAPITestCase, make_request
from frappe.tests.utils import whitelist_for_tests


@whitelist_for_tests(allow_guest=True)
def inspect_request_body():
	request = frappe.request
	state = {
		"data_cached": hasattr(request, "_cached_data"),
		"form_cached": "form" in request.__dict__,
		"max_content_length": request.max_content_length,
	}
	state["body"] = request.stream.read().decode()
	return state


@whitelist_for_tests(allow_guest=True)
def inspect_streaming_query(offset: int):
	request = frappe.request
	return {
		"offset": offset,
		"data_cached": hasattr(request, "_cached_data"),
		"form_cached": "form" in request.__dict__,
		"body": request.stream.read().decode(),
	}


@whitelist_for_tests(allow_guest=True)
def inspect_buffered_json(payload: str):
	request = frappe.request
	return {
		"payload": payload,
		"data_cached": hasattr(request, "_cached_data"),
		"max_content_length": request.max_content_length,
	}


class TestStreamingRequestPaths(FrappeAPITestCase):
	endpoint = "/api/method/frappe.tests.test_streaming_request_paths.inspect_request_body"

	def test_matching_path_leaves_body_stream_unread(self):
		configured = frappe._dict({**frappe.get_site_config(), "max_file_size": 8})
		real_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "streaming_request_paths":
				return [self.endpoint]
			return real_get_hooks(hook, *args, **kwargs)

		with (
			patch("frappe.config.get_site_config", return_value=configured),
			patch.object(frappe, "get_hooks", side_effect=get_hooks),
		):
			response: TestResponse = make_request(
				target=self.TEST_CLIENT.open,
				args=(self.endpoint,),
				kwargs={"method": "PUT", "data": b"stream", "content_type": "application/octet-stream"},
			)

		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertEqual(
			response.json["message"],
			{
				"data_cached": False,
				"form_cached": False,
				"max_content_length": None,
				"body": "stream",
			},
		)

	def test_matching_rpc_keeps_query_arguments_without_buffering_body(self):
		endpoint = "/api/method/frappe.tests.test_streaming_request_paths.inspect_streaming_query"
		real_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "streaming_request_paths":
				return [endpoint]
			return real_get_hooks(hook, *args, **kwargs)

		with patch.object(frappe, "get_hooks", side_effect=get_hooks):
			response: TestResponse = make_request(
				target=self.TEST_CLIENT.open,
				args=(f"{endpoint}?offset=17&_=cachebuster",),
				kwargs={
					"method": "PUT",
					"data": b"stream",
					"content_type": "application/octet-stream",
				},
			)

		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertEqual(
			response.json["message"],
			{
				"offset": 17,
				"data_cached": False,
				"form_cached": False,
				"body": "stream",
			},
		)

	def test_matching_post_keeps_json_body_parsing_and_cap(self):
		endpoint = "/api/method/frappe.tests.test_streaming_request_paths.inspect_buffered_json"
		configured = frappe._dict({**frappe.get_site_config(), "max_file_size": 1024})
		real_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "streaming_request_paths":
				return [endpoint]
			return real_get_hooks(hook, *args, **kwargs)

		with (
			patch("frappe.config.get_site_config", return_value=configured),
			patch.object(frappe, "get_hooks", side_effect=get_hooks),
		):
			response: TestResponse = make_request(
				target=self.TEST_CLIENT.open,
				args=(endpoint,),
				kwargs={"method": "POST", "json": {"payload": "finish"}},
			)

		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertEqual(
			response.json["message"],
			{
				"payload": "finish",
				"data_cached": True,
				"max_content_length": 1024,
			},
		)

	def test_configured_prefix_does_not_match_a_sibling_route(self):
		configured = frappe._dict({**frappe.get_site_config(), "max_file_size": 8})
		real_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "streaming_request_paths":
				return [self.endpoint.removesuffix("_request_body")]
			return real_get_hooks(hook, *args, **kwargs)

		with (
			patch("frappe.config.get_site_config", return_value=configured),
			patch.object(frappe, "get_hooks", side_effect=get_hooks),
		):
			response: TestResponse = make_request(
				target=self.TEST_CLIENT.open,
				args=(self.endpoint,),
				kwargs={"method": "PUT", "data": b"buffer", "content_type": "application/octet-stream"},
			)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.json["message"],
			{
				"data_cached": True,
				"form_cached": True,
				"max_content_length": 8,
				"body": "buffer",
			},
		)

	def test_body_cap_still_applies_outside_streaming_paths(self):
		configured = frappe._dict({**frappe.get_site_config(), "max_file_size": 8})
		real_get_hooks = frappe.get_hooks
		streaming_paths = ["/api/"]

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "streaming_request_paths":
				return streaming_paths
			return real_get_hooks(hook, *args, **kwargs)

		with (
			patch("frappe.config.get_site_config", return_value=configured),
			patch.object(frappe, "get_hooks", side_effect=get_hooks),
		):
			streamed: TestResponse = make_request(
				target=self.TEST_CLIENT.open,
				args=(self.endpoint,),
				kwargs={"method": "PUT", "data": b"123456789", "content_type": "application/octet-stream"},
			)
			streaming_paths[:] = ["/elsewhere/"]
			buffered: TestResponse = make_request(
				target=self.TEST_CLIENT.open,
				args=(self.endpoint,),
				kwargs={"method": "PUT", "data": b"123456789", "content_type": "application/octet-stream"},
			)

		self.assertEqual(streamed.status_code, 200)
		self.assertEqual(streamed.json["message"]["body"], "123456789")
		self.assertEqual(buffered.status_code, 413)
