# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The flow server's session verbs, spoken over its unix socket as one site."""

from __future__ import annotations

from typing import Any

import httpx

TIMEOUT = 15


class DaemonError(Exception):
	"""The flow server refused or failed a call. `status` is None when it was unreachable."""

	def __init__(self, status: int | None, detail: Any):
		super().__init__(
			f"flow server {status}: {detail}" if status else f"flow server unreachable: {detail}"
		)
		self.status = status
		self.detail = detail


class DaemonClient:
	def __init__(
		self,
		socket_path: str,
		token: str | None = None,
		*,
		site: str | None = None,
		transport: httpx.BaseTransport | None = None,
	):
		headers = {"Authorization": f"Bearer {token}"} if token else {}
		if site:
			headers["X-Flow-Site"] = site
		self._http = httpx.Client(
			transport=transport or httpx.HTTPTransport(uds=socket_path),
			base_url="http://flow-server",
			headers=headers,
		)

	@classmethod
	def for_site(cls) -> DaemonClient:
		"""This site's client: the bench daemon's socket, the site's name and secret."""
		import frappe
		from frappe.flow.daemon import lifecycle

		if not frappe.conf.flow_server_secret:
			raise DaemonError(None, "this site is not provisioned; run `bench flow-server setup`")
		return cls(str(lifecycle.socket_path()), frappe.conf.flow_server_secret, site=frappe.local.site)

	def __enter__(self) -> DaemonClient:
		return self

	def __exit__(self, *exc: object) -> None:
		self.close()

	def close(self) -> None:
		self._http.close()

	def _call(self, method: str, path: str, *, timeout: float = TIMEOUT, **request: Any) -> Any:
		try:
			response = self._http.request(method, path, timeout=timeout, **request)
		except httpx.HTTPError as exc:
			raise DaemonError(None, f"{type(exc).__name__}: {exc}") from None
		if response.is_error:
			raise DaemonError(response.status_code, _detail(response))
		return response.json()

	# --- daemon ---------------------------------------------------------

	def healthz(self) -> dict:
		return self._call("GET", "/healthz")

	# --- sessions -------------------------------------------------------

	def create_session(self, config: dict) -> dict:
		return self._call("POST", "/sessions", json=config)

	def get_session(self, sid: str) -> dict:
		return self._call("GET", f"/sessions/{sid}")

	def delete_session(self, sid: str) -> dict:
		return self._call("DELETE", f"/sessions/{sid}")

	def run(self, sid: str, message: str, *, attachments: list[str] | None = None) -> dict:
		"""Start a turn and return as soon as the daemon accepts it."""
		body = {"message": message, "attachments": attachments or []}
		return self._call("POST", f"/sessions/{sid}/run", json=body)

	def resume(self, sid: str, answers: dict[str, str], *, approval_seq: int) -> dict:
		body = {"approval_seq": approval_seq, "answers": answers}
		return self._call("POST", f"/sessions/{sid}/resume", json=body)

	def abort(self, sid: str) -> dict:
		return self._call("POST", f"/sessions/{sid}/abort")

	def cancel_pending(self, sid: str) -> dict:
		return self._call("POST", f"/sessions/{sid}/cancel_pending")

	def rewind(self, sid: str, target_seq: int) -> dict:
		return self._call("POST", f"/sessions/{sid}/rewind", json={"target_seq": target_seq})

	def compact(self, sid: str) -> dict:
		"""Start summarizing the conversation; it runs as a turn of its own."""
		return self._call("POST", f"/sessions/{sid}/compact")

	def tool_waiting(self, sid: str, token: str) -> dict:
		return self._call("POST", f"/sessions/{sid}/tool_waiting", json={"token": token})

	def tool_result(self, sid: str, token: str, result: dict) -> dict:
		"""Hand a background tool's result to the call waiting on `token`."""
		return self._call("POST", f"/sessions/{sid}/tool_result", json={"token": token, **result})

	def set_model(
		self,
		sid: str,
		model: str,
		*,
		api_key: str | None = None,
		api_base: str | None = None,
		model_params: dict | None = None,
		reasoning_effort: str | None = None,
	) -> dict:
		body = {
			"model": model,
			"api_key": api_key,
			"api_base": api_base,
			"reasoning_effort": reasoning_effort,
		}
		if model_params:
			body["model_params"] = model_params
		return self._call("POST", f"/sessions/{sid}/model", json=body)

	def patch_config(
		self,
		sid: str,
		*,
		title: str | None = None,
		auto_approve: bool | None = None,
		tools: list[str] | None = None,
		client_tools: list[dict] | None = None,
		confirm_tools: list[str] | None = None,
	) -> dict:
		body = {"title": title, "auto_approve": auto_approve}
		if tools is not None:
			body["tools"] = tools
		if client_tools is not None:
			body["client_tools"] = client_tools
		if confirm_tools is not None:
			body["confirm_tools"] = confirm_tools
		return self._call("PATCH", f"/sessions/{sid}/config", json=body)

	def entries(self, sid: str, *, since: int = 0, path: str = "active") -> dict:
		return self._call("GET", f"/sessions/{sid}/entries", params={"since": since, "path": path})

	def upload_attachments(self, sid: str, files: list[tuple[str, bytes, str]]) -> dict:
		"""`files` are (name, content, mime type) triples."""
		parts = [("files", (name, data, mime)) for name, data, mime in files]
		return self._call("POST", f"/sessions/{sid}/attachments", files=parts)

	def cleanup_attachments(self, sid: str, attachment_ids: list[str]) -> dict:
		body = {"attachments": attachment_ids}
		return self._call("DELETE", f"/sessions/{sid}/attachments", json=body)


def _detail(response: httpx.Response) -> Any:
	"""The daemon's own explanation. A validation error echoes the request, which may
	carry a model key, so only the field paths and messages are kept."""
	try:
		body = response.json()
	except ValueError:
		return response.text[:500]
	detail = body.get("detail", body) if isinstance(body, dict) else body
	if isinstance(detail, list):
		return [{"loc": item.get("loc"), "msg": item.get("msg")} for item in detail if isinstance(item, dict)]
	return detail
