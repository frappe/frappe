# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Signing at email egress.

Stored content holds stable, unsigned ``/f/<blob>/<filename>`` URLs (see the
spec section "Embedded URLs"). Outgoing email HTML is rewritten at send time:
each unsigned private-blob URL becomes an absolute signed URL with a long TTL,
so external recipients can open the file without a session.

TTL comes from the ``storage_email_url_ttl`` site config (seconds), default
30 days. A failed rewrite never blocks sending: the original HTML is returned.
"""

import re
import time
from urllib.parse import parse_qs, unquote

import frappe
from frappe.utils import get_url

DEFAULT_EMAIL_URL_TTL = 30 * 24 * 60 * 60  # 30 days, in seconds

# href/src attributes holding a relative or absolute /f/<blob>/<filename> URL
F_URL_PATTERN = re.compile(
	r"""(?P<attr>href|src)\s*=\s*(?P<q>["'])"""
	r"""(?P<prefix>https?://[^"'\s]*?)?"""
	r"""/f/(?P<blob>[^/"'?#\s]+)/(?P<filename>[^"'?#\s]+)"""
	r"""(?P<query>\?[^"'\s]*)?"""
	r"""(?P=q)""",
	re.IGNORECASE,
)

# bare /f/<blob>/<filename> URLs in a plain-text body
TEXT_F_URL_PATTERN = re.compile(
	r"""(?P<prefix>https?://[^\s"'<>]*?)?"""
	r"""/f/(?P<blob>[^/\s"'?#<>]+)/(?P<filename>[^\s"'?#<>]+)"""
	r"""(?P<query>\?[^\s"'<>]*)?""",
	re.IGNORECASE,
)


def get_email_url_ttl() -> int:
	from frappe.utils import cint

	return cint(frappe.conf.get("storage_email_url_ttl")) or DEFAULT_EMAIL_URL_TTL


def rewrite_urls_for_email(html: str) -> str:
	"""Replace unsigned ``/f/`` URLs in href/src with absolute signed URLs.

	No-op when storage v2 is off or ``html`` is falsy. Already-signed URLs
	(``e=`` and ``s=`` present) and unknown blob names pass through untouched.
	Never raises: on any failure the original HTML is returned."""
	import frappe.storage

	if not html or not frappe.storage.enabled():
		return html

	try:
		rewriter = _Rewriter()
		return F_URL_PATTERN.sub(rewriter.rewrite_match, html)
	except Exception:
		frappe.logger("storage").exception("Failed to sign storage URLs for email")
		return html


def rewrite_text_urls_for_email(text: str) -> str:
	"""Sign bare ``/f/`` URLs in an explicit plain-text email body.

	Same behavior as ``rewrite_urls_for_email``, for text parts that never
	pass through the HTML formatter."""
	import frappe.storage

	if not text or not frappe.storage.enabled():
		return text

	try:
		rewriter = _Rewriter()
		return TEXT_F_URL_PATTERN.sub(rewriter.rewrite_text_match, text)
	except Exception:
		frappe.logger("storage").exception("Failed to sign storage URLs for email text")
		return text


class _Rewriter:
	"""Per-call rewrite state: site URL, TTL, and a blob-existence cache."""

	def __init__(self):
		self.site_url = get_url().rstrip("/")
		self.ttl = get_email_url_ttl()
		self._known_blobs: dict[str, bool] = {}

	def rewrite_match(self, match: re.Match) -> str:
		try:
			url = self._signed_url(match)
			if url is None:
				return match.group(0)
			quote_char = match.group("q")
			attr = match.group("attr")
			return f"{attr}={quote_char}{url}{quote_char}"
		except Exception:
			frappe.logger("storage").exception("Failed to sign a storage URL for email")
			return match.group(0)

	def rewrite_text_match(self, match: re.Match) -> str:
		try:
			url = self._signed_url(match)
			return match.group(0) if url is None else url
		except Exception:
			frappe.logger("storage").exception("Failed to sign a storage URL for email")
			return match.group(0)

	def _signed_url(self, match: re.Match) -> str | None:
		"""Signed absolute URL for a matched /f/ reference, or None to keep it."""
		from frappe.storage.url import make_signature

		query = match.group("query") or ""
		if is_signed_query(query):
			return None

		prefix = match.group("prefix")
		if prefix and prefix.rstrip("/") != self.site_url:
			# /f/ URL on a foreign host: not ours to sign
			return None

		blob_name = match.group("blob")
		if not self.blob_exists(blob_name):
			return None

		filename = match.group("filename")
		expires = int(time.time()) + self.ttl
		# serve.py verifies against the URL-decoded filename
		signature = make_signature(blob_name, unquote(filename), expires)
		return f"{self.site_url}/f/{blob_name}/{filename}?e={expires}&s={signature}"

	def blob_exists(self, blob_name: str) -> bool:
		if blob_name not in self._known_blobs:
			self._known_blobs[blob_name] = bool(frappe.db.exists("File Blob", blob_name))
		return self._known_blobs[blob_name]


def is_signed_query(query: str) -> bool:
	params = parse_qs(query.lstrip("?"))
	return bool(params.get("e") and params.get("s"))
