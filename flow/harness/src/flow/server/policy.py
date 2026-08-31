"""Operator-set server policy: which tools and route groups this daemon offers.

The default policy is fully permissive — the local harness, unchanged. `--profile
deployed` hardens a daemon that fronts a remote client (e.g. a Frappe site): tools
are capped to the read-only pair, and every route group outside the core session
verbs answers 403.
"""

from __future__ import annotations

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
		fs_api: /fs/* and the session file diff; 403 when off.
		providers_api: /models and /providers*; 403 when off.
		extensions_api: Extension reload and info routes; 403 when off.
		skills_api: Skill discovery routes; 403 when off.
	"""

	profile: str = "local"
	tool_allowlist: frozenset[str] | None = None
	callback_hosts: frozenset[str] | None = None
	require_auth: bool = False
	fs_api: bool = True
	providers_api: bool = True
	extensions_api: bool = True
	skills_api: bool = True


# Only the session verbs the remote client actually uses stay on; everything that
# reads or mutates the host directly is off.
DEPLOYED = ServerPolicy(
	profile="deployed",
	tool_allowlist=frozenset({"read_file", "grep"}),
	callback_hosts=frozenset(),
	require_auth=True,
	fs_api=False,
	providers_api=False,
	extensions_api=False,
	skills_api=False,
)


def resolve_policy(profile: str, *, callback_hosts: Collection[str] = ()) -> ServerPolicy:
	"""`callback_hosts` (FLOW_CALLBACK_HOSTS) fills the callback allowlist of a
	profile that restricts callbacks; a permissive profile ignores it."""
	if profile == "local":
		policy = ServerPolicy()
	elif profile == "deployed":
		policy = DEPLOYED
	else:
		raise ValueError(f"unknown profile {profile!r} (expected one of: {', '.join(PROFILES)})")
	if policy.callback_hosts is not None and callback_hosts:
		policy = replace(policy, callback_hosts=frozenset(callback_hosts))
	return policy


def gate(allowed: bool) -> list[params.Depends]:
	"""Route dependencies for one policy switch: none when on, a 403 guard when off.

	The guard runs before the handler, so a gated route never touches its inputs."""
	if allowed:
		return []

	async def refuse() -> None:
		raise HTTPException(status_code=403, detail="disabled by server policy")

	return [Depends(refuse)]
