"""Operator-set server policy: which tools and route groups this daemon offers.

The default policy is fully permissive — the local harness, unchanged. `--profile
deployed` hardens a daemon that fronts a remote client (e.g. a Frappe site): tools
are capped to the read-only pair, and every route group outside the core session
verbs answers 403.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, params

PROFILES = ("local", "deployed")


@dataclass(frozen=True)
class ServerPolicy:
	"""Switches resolved once at startup. Every default is today's permissive behavior,
	so a policy-less daemon behaves exactly as before."""

	profile: str = "local"
	# Cap on the tools any session may compose — builtin and extension tools alike.
	# None = uncapped: sessions pick their own subset, as always.
	tool_allowlist: frozenset[str] | None = None
	fs_api: bool = True  # /fs/* and the session file diff: direct filesystem access
	providers_api: bool = True  # /models and /providers* (daemon-held credentials)
	extensions_api: bool = True  # extension reload and info routes
	skills_api: bool = True  # skill discovery routes


# Only the session verbs the remote client actually uses stay on; everything that
# reads or mutates the host directly is off.
DEPLOYED = ServerPolicy(
	profile="deployed",
	tool_allowlist=frozenset({"read_file", "grep"}),
	fs_api=False,
	providers_api=False,
	extensions_api=False,
	skills_api=False,
)


def resolve_policy(profile: str) -> ServerPolicy:
	if profile == "local":
		return ServerPolicy()
	if profile == "deployed":
		return DEPLOYED
	raise ValueError(f"unknown profile {profile!r} (expected one of: {', '.join(PROFILES)})")


def gate(allowed: bool) -> list[params.Depends]:
	"""Route dependencies for one policy switch: none when on, a 403 guard when off.

	The guard runs before the handler, so a gated route never touches its inputs."""
	if allowed:
		return []

	async def refuse() -> None:
		raise HTTPException(status_code=403, detail="disabled by server policy")

	return [Depends(refuse)]
