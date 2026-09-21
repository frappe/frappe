"""Multi-tenant mode: one daemon serving many sites (a Frappe bench).

The tenants file maps each site to its bearer token. A request's token names its
site, and every session verb then acts on that site's own store partition
(`data_dir/tenants/<site>`, or the site's own `data_dir`), so sites can never see
each other's sessions.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Tenant:
	"""One site this daemon serves, as declared in `FLOW_TENANTS_FILE`.

	Attributes:
		site: Site name; also the on-disk partition `data_dir/tenants/<site>`.
		token: Bearer token that authenticates requests as this site.
		allowed_roots: Path fence for this site's sessions. The tenants file
			requires it; None (programmatic use) inherits the daemon-wide roots.
		ignore_hidden_files: Whether dot-prefixed descendants of allowed roots are hidden.
		callback_hosts: host[:port] values a session callback_url may target,
			replacing FLOW_CALLBACK_HOSTS for this site. None inherits it; an
			empty list refuses callbacks.
		data_dir: This site's own partition directory; None means `data_dir/tenants/<site>`.
	"""

	site: str
	token: str
	allowed_roots: tuple[str, ...] | None = None
	callback_hosts: tuple[str, ...] | None = None
	ignore_hidden_files: bool = False
	data_dir: str | None = None


def load_tenants(path: str) -> list[Tenant]:
	"""Parse `{"<site>": {"token": "...", "allowed_roots": ["..."], "callback_hosts": ["..."]}}`.

	Strict on shape — a typo must fail loudly, not silently drop a fence."""
	with open(path, encoding="utf-8") as file:
		data = json.load(file)
	if not isinstance(data, dict) or not data:
		raise ValueError("tenants file must be a non-empty JSON object keyed by site")
	tenants: list[Tenant] = []
	tokens: set[str] = set()
	dirs: set[str | None] = set()
	for site, entry in data.items():
		tenant = _parse_entry(site, entry)
		if tenant.token in tokens:
			raise ValueError(f"site {site!r} reuses another site's token")
		if tenant.data_dir is not None and tenant.data_dir in dirs:
			raise ValueError(f"site {site!r} reuses another site's data_dir")
		tokens.add(tenant.token)
		dirs.add(tenant.data_dir)
		tenants.append(tenant)
	return tenants


def _parse_entry(site: str, entry: object) -> Tenant:
	if not isinstance(entry, dict):
		raise ValueError(f"site {site!r}: entry must be a JSON object")
	unknown = sorted(
		str(key)
		for key in entry
		if key not in ("token", "allowed_roots", "ignore_hidden_files", "callback_hosts", "data_dir")
	)
	if unknown:
		raise ValueError(f"site {site!r}: unknown keys: {', '.join(unknown)}")
	token = entry.get("token")
	if not isinstance(token, str) or not token.strip():
		raise ValueError(f"site {site!r}: token must be a non-empty string")
	roots = entry.get("allowed_roots")
	if roots is None:
		raise ValueError(f"site {site!r}: allowed_roots is required — a non-empty list of paths")
	bad_roots = f"site {site!r}: allowed_roots must be a non-empty list of paths"
	if not isinstance(roots, list) or not roots:
		raise ValueError(bad_roots)
	values = tuple(root for root in roots if isinstance(root, str) and root)
	if len(values) != len(roots):
		raise ValueError(bad_roots)
	ignore_hidden_files = entry.get("ignore_hidden_files", False)
	if not isinstance(ignore_hidden_files, bool):
		raise ValueError(f"site {site!r}: ignore_hidden_files must be a boolean")
	hosts = entry.get("callback_hosts")
	parsed = None
	if hosts is not None:
		bad_hosts = f"site {site!r}: callback_hosts must be a list of host[:port] strings"
		if not isinstance(hosts, list):
			raise ValueError(bad_hosts)
		parsed = tuple(host for host in hosts if isinstance(host, str) and host)
		if len(parsed) != len(hosts):
			raise ValueError(bad_hosts)
	data_dir = entry.get("data_dir")
	if data_dir is not None and (not isinstance(data_dir, str) or not os.path.isabs(data_dir)):
		raise ValueError(f"site {site!r}: data_dir must be an absolute path")
	return Tenant(
		site=site,
		token=token,
		allowed_roots=values,
		ignore_hidden_files=ignore_hidden_files,
		callback_hosts=parsed,
		data_dir=data_dir,
	)
