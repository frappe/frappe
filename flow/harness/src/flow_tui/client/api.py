"""FlowClient — a thin async httpx wrapper over the daemon's HTTP API.

One typed method per endpoint; payload shapes come straight from `flow` (SessionConfig,
event models) so there is no parallel contract to keep in sync. Any non-2xx answer
becomes a `FlowAPIError` carrying the status code and the server's `detail`.
"""

from __future__ import annotations

from typing import Literal

import httpx

from flow_harness.events import ReasoningEffort
from flow_harness.session.config import SessionConfig

# SSE reads block between events; keepalives arrive every 15 s while the session
# idles, so a 60 s read timeout only fires when the peer is truly gone.
_STREAM_TIMEOUT = httpx.Timeout(30.0, read=60.0)


class FlowAPIError(Exception):
	"""The server answered with an error status."""

	def __init__(self, status_code: int, detail: object):
		self.status_code = status_code
		self.detail = detail
		super().__init__(f"HTTP {status_code}: {detail}")


class FlowClient:
	def __init__(
		self,
		base_url: str,
		token: str | None = None,
		*,
		timeout: float = 30.0,
		uds: str | None = None,
		transport: httpx.AsyncBaseTransport | None = None,
	):
		headers = {"Authorization": f"Bearer {token}"} if token else {}
		if uds is not None and transport is None:
			transport = httpx.AsyncHTTPTransport(uds=uds)
		self._http = httpx.AsyncClient(
			base_url=base_url, headers=headers, timeout=timeout, transport=transport
		)

	async def aclose(self) -> None:
		await self._http.aclose()

	async def __aenter__(self) -> "FlowClient":
		return self

	async def __aexit__(self, *exc_info) -> None:
		await self.aclose()

	# --- endpoints --------------------------------------------------------

	async def healthz(self) -> bool:
		try:
			return (await self._http.get("/healthz")).json() == {"ok": True}
		except httpx.TransportError:
			return False

	async def list_models(self) -> dict:
		"""The discovered model catalog: `{"models": [...], "errors": [...]}`."""
		return await self._request("GET", "/models")

	async def list_sessions(self) -> list[dict]:
		return (await self._request("GET", "/sessions"))["sessions"]

	async def create_session(self, config: SessionConfig) -> str:
		data = await self._request("POST", "/sessions", json=config.model_dump(mode="json"))
		return data["session_id"]

	async def get_session(self, sid: str) -> dict:
		return await self._request("GET", f"/sessions/{sid}")

	async def skills(self, sid: str) -> dict:
		return await self._request("GET", f"/sessions/{sid}/skills")

	async def run(self, sid: str, message: str, *, wait: bool = False) -> dict:
		return await self._request(
			"POST", f"/sessions/{sid}/run", json={"message": message}, params=_wait(wait)
		)

	async def resume(
		self, sid: str, *, approval_seq: int, answers: dict[str, str], wait: bool = False
	) -> dict:
		return await self._request(
			"POST",
			f"/sessions/{sid}/resume",
			json={"approval_seq": approval_seq, "answers": answers},
			params=_wait(wait),
		)

	async def abort(self, sid: str) -> dict:
		return await self._request("POST", f"/sessions/{sid}/abort")

	async def reload_extensions(self) -> dict:
		return await self._request("POST", "/extensions/reload")

	async def rewind(self, sid: str, target_seq: int) -> dict:
		return await self._request("POST", f"/sessions/{sid}/rewind", json={"target_seq": target_seq})

	async def set_model(
		self,
		sid: str,
		model: str,
		*,
		credential_id: str | None = None,
		reasoning_effort: ReasoningEffort | None = None,
	) -> dict:
		return await self._request(
			"POST",
			f"/sessions/{sid}/model",
			json={"model": model, "credential_id": credential_id, "reasoning_effort": reasoning_effort},
		)

	async def cancel_pending(self, sid: str) -> dict:
		return await self._request("POST", f"/sessions/{sid}/cancel_pending")

	async def entries(self, sid: str, *, since: int = 0, path: Literal["active", "all"] = "active") -> dict:
		return await self._request("GET", f"/sessions/{sid}/entries", params={"since": since, "path": path})

	def sse(self, sid: str, *, since: int = 0, follow: bool = True):
		"""Open the SSE stream. Returns the httpx stream context manager; `EventStream`
		owns parsing, cursor tracking, and reconnects — use it instead of this."""
		return self._http.stream(
			"GET",
			f"/sessions/{sid}/stream",
			params={"since": since, "follow": str(follow).lower()},
			timeout=_STREAM_TIMEOUT,
		)

	# --- plumbing ---------------------------------------------------------

	async def _request(self, method: str, url: str, **kwargs) -> dict:
		response = await self._http.request(method, url, **kwargs)
		if response.is_error:
			try:
				detail = response.json().get("detail", response.text)
			except ValueError:
				detail = response.text
			raise FlowAPIError(response.status_code, detail)
		return response.json()


def _wait(wait: bool) -> dict:
	return {"wait": "true"} if wait else {}
