"""Operator-set server policy: which tools and route groups this daemon offers.

The default policy is fully permissive — the local harness, unchanged. `--profile
deployed` hardens a daemon that fronts a remote client (e.g. a Frappe site): tools
are capped to the read-only pair, and every route group outside the core session
verbs answers 403.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass, replace

from fastapi import Depends, HTTPException, params

PROFILES = ("local", "deployed")


@dataclass(frozen=True)
class ServerPolicy:
	"""Switches resolved once at startup. Every default is today's permissive behavior,
	so a policy-less daemon behaves exactly as before.

	Attributes:
		profile: Name of the preset this policy came from.
		tool_allowlist: Cap on the tools any session may compose, builtin and
			extension alike. None = uncapped.
		callback_hosts: host[:port] values a session callback_url may target.
			None = any; an empty set refuses client callbacks.
		require_auth: Refuse to serve without a bearer token, even on loopback or
			a unix socket.
		inline_credentials: Accept `api_key`, `api_base` and `model_params` on session
			create and set-model; a request carrying them is a 400 when off.
		extensions: Load extensions from the global extensions directory (arbitrary
			operator Python) and serve the extension reload/info routes (403 when
			off). Explicit `--extension` paths always load.
		max_request_bytes: Largest accepted request body; a bigger one is a 413.
			None = unlimited.
		audit_log: Append one JSONL row per sensitive call (mutations and auth
			refusals) to `<data_dir>/audit.jsonl`.
		fs_api: /fs/* and the session file diff; 403 when off.
		providers_api: /models and /providers*; 403 when off.
		skills_api: Skill discovery routes; 403 when off.
		tools_api: `/tools`, the list of tools a session may enable; 403 when off.
		settings_api: `/settings`, the web UI's preferences in `~/.flow/settings.json`;
			403 when off.
		workspaces_api: `/workspaces`, the web UI's named folders; 403 when off.
	"""

	profile: str = "local"
	tool_allowlist: frozenset[str] | None = None
	callback_hosts: frozenset[str] | None = None
	require_auth: bool = False
	inline_credentials: bool = False
	extensions: bool = True
	max_request_bytes: int | None = None
	audit_log: bool = False
	fs_api: bool = True
	providers_api: bool = True
	skills_api: bool = True
	tools_api: bool = True
	settings_api: bool = True
	workspaces_api: bool = True


# Only the session verbs the remote client actually uses stay on; everything that
# reads or mutates the host directly is off.
DEPLOYED = ServerPolicy(
	profile="deployed",
	tool_allowlist=frozenset({"read", "grep"}),
	callback_hosts=frozenset(),
	require_auth=True,
	inline_credentials=True,
	extensions=False,
	# fits the largest legitimate request — a full attachment batch (10 files of 20 MiB)
	# plus multipart overhead — while still refusing runaway bodies
	max_request_bytes=224 * 1024 * 1024,
	audit_log=True,
	fs_api=False,
	providers_api=False,
	skills_api=False,
	tools_api=False,
	settings_api=False,
	workspaces_api=False,
)


def resolve_policy(
	profile: str, *, callback_hosts: Collection[str] = (), overrides: str | None = None
) -> ServerPolicy:
	"""`callback_hosts` (FLOW_CALLBACK_HOSTS) fills the callback allowlist of a
	profile that restricts callbacks; a permissive profile ignores it. `overrides`
	(FLOW_POLICY) then overrides individual fields of the result, whatever the
	profile — the operator's last word."""
	if profile == "local":
		policy = ServerPolicy()
	elif profile == "deployed":
		policy = DEPLOYED
	else:
		raise ValueError(f"unknown profile {profile!r} (expected one of: {', '.join(PROFILES)})")
	if policy.callback_hosts is not None and callback_hosts:
		policy = replace(policy, callback_hosts=frozenset(callback_hosts))
	if overrides:
		policy = _apply_overrides(policy, overrides)
	return policy


_BOOL_FIELDS = frozenset(
	{
		"require_auth",
		"inline_credentials",
		"extensions",
		"audit_log",
		"fs_api",
		"providers_api",
		"skills_api",
		"tools_api",
		"settings_api",
		"workspaces_api",
	}
)

# overrides may turn these on, never off — dropping them means choosing another profile
_NO_WEAKENING = frozenset({"require_auth", "audit_log"})


def _apply_overrides(policy: ServerPolicy, raw: str) -> ServerPolicy:
	"""FLOW_POLICY: a JSON object overriding individual policy fields, e.g.
	`{"skills_api": true, "tool_allowlist": ["read", "grep", "bash"]}`.
	Strict on names and types — a typo must fail startup, not silently drop a fence."""
	try:
		data = json.loads(raw)
	except ValueError as e:
		raise ValueError(f"FLOW_POLICY is not valid JSON: {e}") from None
	if not isinstance(data, dict):
		raise ValueError("FLOW_POLICY must be a JSON object of policy fields")
	changes: dict = {}
	for key, value in data.items():
		if key in _BOOL_FIELDS:
			if not isinstance(value, bool):
				raise ValueError(f"FLOW_POLICY: {key} must be true or false")
			locked = key in _NO_WEAKENING and getattr(policy, key)
			if locked and value is False:
				raise ValueError(
					f"FLOW_POLICY: cannot turn off {key} — the {policy.profile!r} profile guarantees it"
				)
		elif key in ("tool_allowlist", "callback_hosts"):
			if value is not None:
				if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
					raise ValueError(f"FLOW_POLICY: {key} must be a list of strings or null")
				value = frozenset(value)
		elif key == "max_request_bytes":
			if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
				raise ValueError(f"FLOW_POLICY: {key} must be a positive integer or null")
		else:
			raise ValueError(f"FLOW_POLICY: unknown policy field {key!r}")
		changes[key] = value
	return replace(policy, **changes)


def gate(allowed: bool) -> list[params.Depends]:
	"""Route dependencies for one policy switch: none when on, a 403 guard when off.

	The guard runs before the handler, so a gated route never touches its inputs."""
	if allowed:
		return []

	async def refuse() -> None:
		raise HTTPException(status_code=403, detail="disabled by server policy")

	return [Depends(refuse)]
