"""Multi-tenant mode: one daemon serving many sites (a Frappe bench).

A request names its site in `X-Flow-Site` and sends the token from that site's own
file; other settings come from one template where `{site}` is the name. Each site has
its own store partition, so sites never see each other's sessions.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field

SITE_HEADER = "X-Flow-Site"
_SITE = "{site}"
# the store's rule for site names, which fill file paths
_SITE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_KEYS = (
	"token_file",
	"token_key",
	"allowed_roots",
	"ignore_hidden_files",
	"callback_hosts",
	"callback_headers",
	"data_dir",
	"extensions",
)


@dataclass(frozen=True)
class Tenant:
	"""One site this daemon serves.

	Attributes:
		site: Site name; also the on-disk partition `data_dir/tenants/<site>`.
		token: Bearer token that authenticates requests as this site.
		allowed_roots: Path fence for this site's sessions; None inherits the daemon-wide roots.
		callback_hosts: host[:port] values a session callback_url may target,
			replacing FLOW_CALLBACK_HOSTS for this site. None inherits it; an
			empty list refuses callbacks.
		callback_headers: Headers added to every callback, over the session's own.
		ignore_hidden_files: Whether dot-prefixed descendants of allowed roots are hidden.
		data_dir: This site's own partition directory; None means `data_dir/tenants/<site>`.
		extensions: Extension files or directories loaded for this site alone, on top of
			the daemon's own; one that does not exist yet is skipped.
	"""

	site: str
	token: str
	allowed_roots: tuple[str, ...] | None = None
	callback_hosts: tuple[str, ...] | None = None
	callback_headers: dict[str, str] = field(default_factory=dict)
	ignore_hidden_files: bool = False
	data_dir: str | None = None
	extensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class TenantTemplate:
	"""Every site's settings as one template; `{site}` stands for the site name.

	Attributes:
		token_file: JSON file holding a site's token.
		token_key: The token's key in that file.
		allowed_roots, callback_hosts, callback_headers, ignore_hidden_files, data_dir,
			extensions: As on Tenant.
	"""

	token_file: str
	token_key: str
	allowed_roots: tuple[str, ...] | None = None
	callback_hosts: tuple[str, ...] | None = None
	callback_headers: dict[str, str] = field(default_factory=dict)
	ignore_hidden_files: bool = False
	data_dir: str | None = None
	extensions: tuple[str, ...] = ()

	def lookup(self, site: str) -> Tenant | None:
		"""The named site's tenant, or None if it has no token."""
		if not _SITE_RE.match(site):
			return None
		token = self._token(_fill(self.token_file, site))
		if token is None:
			return None

		def fill(value: str) -> str:
			return _fill(value, site)

		return Tenant(
			site=site,
			token=token,
			allowed_roots=None if self.allowed_roots is None else tuple(map(fill, self.allowed_roots)),
			callback_hosts=None if self.callback_hosts is None else tuple(map(fill, self.callback_hosts)),
			callback_headers={key: fill(value) for key, value in self.callback_headers.items()},
			ignore_hidden_files=self.ignore_hidden_files,
			data_dir=None if self.data_dir is None else fill(self.data_dir),
			extensions=tuple(map(fill, self.extensions)),
		)

	def sites(self) -> list[str]:
		"""Every site with a token file."""
		pattern = "*".join(glob.escape(part) for part in self.token_file.split(_SITE))
		names = {_site_from_path(self.token_file, path) for path in glob.glob(pattern)}
		return sorted(name for name in names if name and _SITE_RE.match(name))

	def path_for_site(self, site: str, path: str) -> str:
		"""`path` as `site`'s folder when it is another site's (after a rename or copy)."""
		for root in self.allowed_roots or ():
			if _site_from_path(root, path):
				return _fill(root, site)
		return path

	def _token(self, path: str) -> str | None:
		try:
			with open(path, encoding="utf-8") as file:
				data = json.load(file)
		except (OSError, ValueError):
			return None
		token = data.get(self.token_key) if isinstance(data, dict) else None
		return token if isinstance(token, str) and token else None


def load_tenants(raw: str) -> TenantTemplate:
	"""Parse FLOW_TENANTS, e.g. `{"token_file": "/bench/sites/{site}/site_config.json",
	"token_key": "flow_server_secret", "allowed_roots": ["/bench/sites/{site}/public/files"]}`.

	Strict on shape — a typo must fail loudly, not silently drop a fence."""
	data = json.loads(raw)
	if not isinstance(data, dict):
		raise ValueError("must be a JSON object")
	unknown = sorted(str(key) for key in data if key not in _KEYS)
	if unknown:
		raise ValueError(f"unknown keys: {', '.join(unknown)}")
	token_file = data.get("token_file")
	if not isinstance(token_file, str) or not os.path.isabs(token_file) or _SITE not in token_file:
		raise ValueError("token_file must be an absolute path containing {site}")
	token_key = data.get("token_key")
	if not isinstance(token_key, str) or not token_key:
		raise ValueError("token_key must be a non-empty string")
	roots = data.get("allowed_roots")
	if not isinstance(roots, list) or not roots or not all(isinstance(r, str) and r for r in roots):
		raise ValueError("allowed_roots is required — a non-empty list of paths")
	hosts = data.get("callback_hosts")
	if hosts is not None and (
		not isinstance(hosts, list) or not all(isinstance(h, str) and h for h in hosts)
	):
		raise ValueError("callback_hosts must be a list of host[:port] strings")
	headers = data.get("callback_headers", {})
	if not isinstance(headers, dict) or not all(isinstance(v, str) for v in headers.values()):
		raise ValueError("callback_headers must map header names to strings")
	ignore_hidden_files = data.get("ignore_hidden_files", False)
	if not isinstance(ignore_hidden_files, bool):
		raise ValueError("ignore_hidden_files must be a boolean")
	data_dir = data.get("data_dir")
	if data_dir is not None and (not isinstance(data_dir, str) or not os.path.isabs(data_dir)):
		raise ValueError("data_dir must be an absolute path")
	if data_dir is not None and _SITE not in data_dir:
		raise ValueError("data_dir must contain {site}, or every site would share one")
	extensions = data.get("extensions", [])
	if not isinstance(extensions, list) or not all(
		isinstance(p, str) and os.path.isabs(p) for p in extensions
	):
		raise ValueError("extensions must be a list of absolute paths")
	return TenantTemplate(
		token_file=token_file,
		token_key=token_key,
		allowed_roots=tuple(roots),
		callback_hosts=None if hosts is None else tuple(hosts),
		callback_headers=headers,
		ignore_hidden_files=ignore_hidden_files,
		data_dir=data_dir,
		extensions=tuple(extensions),
	)


def _fill(value: str, site: str) -> str:
	return value.replace(_SITE, site)


def _site_from_path(value: str, path: str) -> str | None:
	"""The site name in `path` where `value` has `{site}`; None if `path` doesn't fit `value`."""
	head, found, tail = value.partition(_SITE)
	if not found:
		return None
	match = re.fullmatch(re.escape(head) + "(?P<site>[^/]+)" + re.escape(tail), path)
	return match["site"] if match else None
