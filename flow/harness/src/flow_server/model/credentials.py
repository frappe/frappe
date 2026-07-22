"""On-disk store for OAuth/subscription credentials (e.g. Codex).

A single JSON file keyed by provider name, written atomically and locked to 0600 —
these are bearer secrets, so the file is owner-only and never world-readable, even for
the instant between create and chmod (the fd is opened with 0600 up front).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class OAuthCredential:
	access: str
	refresh: str
	expires: int  # epoch milliseconds
	account_id: str | None = None

	def to_dict(self) -> dict:
		data = {
			"type": "oauth",
			"access": self.access,
			"refresh": self.refresh,
			"expires": self.expires,
		}
		if self.account_id:
			data["account_id"] = self.account_id
		return data

	@classmethod
	def from_dict(cls, data: dict) -> OAuthCredential:
		return cls(
			access=data["access"],
			refresh=data["refresh"],
			expires=int(data["expires"]),
			account_id=data.get("account_id"),
		)


class CredentialStore:
	def __init__(self, path: str):
		self.path = path

	def get(self, name: str) -> OAuthCredential | None:
		entry = self._load().get(name)
		if not entry or entry.get("type") != "oauth":
			return None
		return OAuthCredential.from_dict(entry)

	def set(self, name: str, credential: OAuthCredential) -> None:
		data = self._load()
		data[name] = credential.to_dict()
		self._atomic_write(data)

	def delete(self, name: str) -> None:
		data = self._load()
		if name in data:
			del data[name]
			self._atomic_write(data)

	def _load(self) -> dict:
		if not os.path.isfile(self.path):
			return {}
		with open(self.path, encoding="utf-8") as f:
			return json.load(f)

	def _atomic_write(self, data: dict) -> None:
		os.makedirs(os.path.dirname(self.path) or ".", mode=0o700, exist_ok=True)
		tmp = f"{self.path}.tmp"
		fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
		with os.fdopen(fd, "w", encoding="utf-8") as f:
			json.dump(data, f)
		os.chmod(tmp, 0o600)  # force 0600 regardless of umask
		os.replace(tmp, self.path)
