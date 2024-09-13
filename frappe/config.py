import importlib
import json
import os
import signal
import traceback
from typing import Any


class ConfigHandler:
	default_config = (
		("redis_queue", "redis://127.0.0.1:11311"),
		("redis_cache", "redis://127.0.0.1:13311"),
		("db_type", "mariadb"),
		("db_host", "127.0.0.1"),
		("db_port", 3306),
		("db_socket", None),
	)

	def _apply_dynamic_defaults(self):
		if not self._config.get("db_user"):
			self._config["db_user"] = self._config.get("db_name")
		if not self._config.get("db_name"):
			self._config["db_name"] = self._config.get("db_user")
		if self._config.get("db_type") == "postrges":
			self._config["db_port"] = 5432

	def __init__(self, config_path: str):
		self.config_path = config_path
		self._config = None
		self._config_stale = True
		signal.signal(signal.SIGHUP, self._handle_sighup)

	def _handle_sighup(self, signum, frame):
		self._config_stale = True

	@property
	def config(self) -> dict[str, Any]:
		if self._config is None or self._config_stale:
			if os.path.exists(self.config_path):
				with open(self.config_path) as f:
					self._config = json.load(f)
			else:
				self._config = {}
			self._config = dict(self.default_config, **self._config)
			self._update_from_env()
			self._apply_extra_config()
			self._apply_dynamic_defaults()
			self._config_stale = False
		return self._config

	def update_config(self, updates: dict[str, Any]):
		self.config.update(updates)
		with open(self.config_path, "w") as f:
			json.dump(self.config, f, indent=4)
		self._config_stale = True

	def _update_from_env(self):
		for key in self._config.keys():
			env_key = f"FRAPPE_{key.upper()}"
			if env_value := os.environ.get(env_key):
				self._config[key] = env_value

	def _apply_extra_config(self):
		extra_config = self._config.get("extra_config")
		if extra_config:
			if isinstance(extra_config, str):
				extra_config = [extra_config]
			for hook in extra_config:
				try:
					module, method = hook.rsplit(".", 1)
					self._config.update(getattr(importlib.import_module(module), method)())
				except Exception:
					print(f"Config hook {hook} failed")
					traceback.print_exc()
