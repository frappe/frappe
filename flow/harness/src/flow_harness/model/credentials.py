"""User-global provider credentials stored in one owner-only JSON file.

Credentials are keyed by stable provider id and type-tagged. Writes take an OS file
lock, replace the file atomically, and keep both the directory and files private.
"""

from __future__ import annotations

import builtins
import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from tempfile import mkstemp
from typing import Literal

fcntl = None
try:
	import fcntl
except ImportError:
	pass

_PROCESS_LOCKS: dict[str, threading.RLock] = {}


class CredentialStoreError(ValueError):
	pass


@dataclass(frozen=True)
class ApiKeyCredential:
	key: str
	type: Literal["api_key"] = "api_key"

	def to_dict(self) -> dict:
		return {"type": self.type, "key": self.key}


@dataclass(frozen=True)
class OAuthCredential:
	access: str
	refresh: str
	expires: int  # epoch milliseconds
	account_id: str | None = None
	type: Literal["oauth"] = "oauth"

	def to_dict(self) -> dict:
		data = {
			"type": self.type,
			"access": self.access,
			"refresh": self.refresh,
			"expires": self.expires,
		}
		if self.account_id:
			data["account_id"] = self.account_id
		return data


@dataclass(frozen=True)
class CustomProviderCredential:
	"""A user-added OpenAI-compatible endpoint (Ollama, LM Studio, a gateway). It
	carries its own base URL and model ids: there is no static spec for it."""

	name: str
	base_url: str
	models: tuple[str, ...]
	api_key: str | None = None  # local runtimes usually need none
	type: Literal["custom"] = "custom"

	def to_dict(self) -> dict:
		data = {
			"type": self.type,
			"name": self.name,
			"base_url": self.base_url,
			"models": list(self.models),
		}
		if self.api_key:
			data["api_key"] = self.api_key
		return data


Credential = ApiKeyCredential | OAuthCredential | CustomProviderCredential


@dataclass(frozen=True)
class CredentialInfo:
	provider_id: str
	type: Literal["api_key", "oauth", "custom"]


class CredentialStore:
	def __init__(self, path: str):
		self.path = os.path.abspath(os.path.expanduser(path))
		self._lock_path = f"{self.path}.lock"

	def get(self, name: str) -> Credential | None:
		with self._locked():
			entry = self._load_unlocked().get(name)
		return _credential_from_dict(entry) if entry is not None else None

	def get_api_key(self, name: str) -> ApiKeyCredential | None:
		credential = self.get(name)
		return credential if isinstance(credential, ApiKeyCredential) else None

	def get_oauth(self, name: str) -> OAuthCredential | None:
		credential = self.get(name)
		return credential if isinstance(credential, OAuthCredential) else None

	def list(self) -> builtins.list[CredentialInfo]:
		with self._locked():
			data = self._load_unlocked()
		return [
			CredentialInfo(provider_id=name, type=_credential_from_dict(entry).type)
			for name, entry in sorted(data.items())
		]

	def set(self, name: str, credential: Credential) -> None:
		name = _validate_name(name)
		_validate_credential(credential)
		with self._locked():
			data = self._load_unlocked()
			data[name] = credential.to_dict()
			self._atomic_write_unlocked(data)

	def set_api_key(self, name: str, key: str) -> None:
		self.set(name, ApiKeyCredential(key=key.strip()))

	def set_oauth(self, name: str, credential: OAuthCredential) -> None:
		self.set(name, credential)

	def get_custom(self, name: str) -> CustomProviderCredential | None:
		credential = self.get(name)
		return credential if isinstance(credential, CustomProviderCredential) else None

	def set_custom(
		self,
		name: str,
		*,
		display_name: str,
		base_url: str,
		models: tuple[str, ...],
		api_key: str | None = None,
	) -> None:
		self.set(
			name,
			CustomProviderCredential(
				name=display_name.strip(),
				base_url=base_url.strip(),
				models=tuple(model.strip() for model in models),
				api_key=api_key.strip() if api_key and api_key.strip() else None,
			),
		)

	def delete(self, name: str) -> None:
		with self._locked():
			data = self._load_unlocked()
			if name in data:
				del data[name]
				self._atomic_write_unlocked(data)

	@contextmanager
	def _locked(self) -> Iterator[None]:
		with _PROCESS_LOCKS.setdefault(self.path, threading.RLock()):
			parent = os.path.dirname(self.path) or "."
			parent_existed = os.path.isdir(parent)
			os.makedirs(parent, mode=0o700, exist_ok=True)
			if not parent_existed:
				os.chmod(parent, 0o700)
			if os.path.isfile(self.path):
				os.chmod(self.path, 0o600)
			fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o600)
			try:
				os.chmod(self._lock_path, 0o600)
				if fcntl is not None:
					fcntl.flock(fd, fcntl.LOCK_EX)
				yield
			finally:
				if fcntl is not None:
					fcntl.flock(fd, fcntl.LOCK_UN)
				os.close(fd)

	def _load_unlocked(self) -> dict[str, dict]:
		if not os.path.isfile(self.path):
			return {}
		try:
			with open(self.path, encoding="utf-8") as f:
				data = json.load(f)
		except (OSError, json.JSONDecodeError) as e:
			raise CredentialStoreError(f"Could not read credential store: {e}") from e
		if not isinstance(data, dict):
			raise CredentialStoreError("Credential store must contain a JSON object")
		for name, entry in data.items():
			if not isinstance(name, str) or not isinstance(entry, dict):
				raise CredentialStoreError("Credential entries must be provider-keyed objects")
			_credential_from_dict(entry)
		return data

	def _atomic_write_unlocked(self, data: dict[str, dict]) -> None:
		fd, tmp = mkstemp(
			prefix=f".{os.path.basename(self.path)}.",
			dir=os.path.dirname(self.path) or ".",
		)
		try:
			os.chmod(tmp, 0o600)
			with os.fdopen(fd, "w", encoding="utf-8") as f:
				json.dump(data, f, indent=2, sort_keys=True)
				f.write("\n")
			os.replace(tmp, self.path)
		finally:
			if os.path.exists(tmp):
				os.unlink(tmp)


def _credential_from_dict(data: dict) -> Credential:
	kind = data.get("type")
	if kind == "api_key":
		return ApiKeyCredential(key=_required_string(data, "key"))
	if kind == "oauth":
		expires = data.get("expires")
		if not isinstance(expires, int) or isinstance(expires, bool) or expires <= 0:
			raise CredentialStoreError("OAuth credential expiry must be a positive integer")
		account_id = data.get("account_id")
		if account_id is not None and (not isinstance(account_id, str) or not account_id):
			raise CredentialStoreError("OAuth account_id must be a non-empty string")
		return OAuthCredential(
			access=_required_string(data, "access"),
			refresh=_required_string(data, "refresh"),
			expires=expires,
			account_id=account_id,
		)
	if kind == "custom":
		models = data.get("models")
		if not isinstance(models, list) or not models:
			raise CredentialStoreError("Custom provider models must be a non-empty list")
		if any(not isinstance(model, str) or not model.strip() for model in models):
			raise CredentialStoreError("Custom provider models must be non-empty strings")
		api_key = data.get("api_key")
		if api_key is not None and (not isinstance(api_key, str) or not api_key.strip()):
			raise CredentialStoreError("Custom provider API key must be a non-empty string")
		return CustomProviderCredential(
			name=_required_string(data, "name"),
			base_url=_required_string(data, "base_url"),
			models=tuple(model.strip() for model in models),
			api_key=api_key.strip() if api_key else None,
		)
	raise CredentialStoreError(f"Unknown credential type {kind!r}")


def _required_string(data: dict, name: str) -> str:
	value = data.get(name)
	if not isinstance(value, str) or not value.strip():
		raise CredentialStoreError(f"Credential field {name!r} must be a non-empty string")
	return value.strip()


def _validate_name(name: str) -> str:
	if not isinstance(name, str) or not name.strip():
		raise CredentialStoreError("Provider id must be a non-empty string")
	return name.strip()


def _validate_credential(credential: Credential) -> None:
	if isinstance(credential, ApiKeyCredential):
		if not credential.key.strip():
			raise CredentialStoreError("API key must not be empty")
		return
	_credential_from_dict(credential.to_dict())
