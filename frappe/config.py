import importlib
import json
import os
import pprint
import re
import traceback
import warnings
from typing import Any

from filelock import FileLock, Timeout


class FrappeUnregisteredConfigOptionWarning(Warning):
	pass


class ConfigType(dict):
	"""A dictionary subclass that provides attribute-style access to configuration options.

	Warns when accessing unregistered configuration options.
	"""

	def __repr__(self):
		return pprint.pformat(dict(self), indent=2, width=80, sort_dicts=False)

	def __getattr__(self, name):
		if name not in registry.options:
			# filter out noise in ipython console
			if not name.startswith("_ipython") and name != "_repr_mimebundle_":
				warnings.warn(
					f"Accessing unregistered configuration option: {name}",
					FrappeUnregisteredConfigOptionWarning,
					stacklevel=2,
				)
		if name not in self and (default := registry.options.get(name, {}).get("default")):
			if callable(default):
				return default(self)
			return default
		elif name not in self:
			return None
		return self[name]


class ConfigRegistry:
	"""Registry for configuration options with their documentation and default values."""

	def __init__(self):
		self.options: dict[str, dict[str, Any]] = {}

	def register(self, option: str, docstring: str, default: Any):
		self.options[option] = {"docstring": docstring, "default": default}

	def __repr__(self):
		if not self.options:
			return "ConfigRegistry(No options registered)"

		# Find the maximum lengths for formatting
		max_option_length = max(len(option) for option in self.options)
		max_default_length = max(len(self._format_default(opt["default"])) for opt in self.options.values())

		# Create the header
		header = f"{'Option':<{max_option_length}} | {'Default':<{max_default_length}} | Description"
		separator = f"{'-' * max_option_length}-+-{'-' * max_default_length}-+{'-' * 20}"

		# Create the table rows
		rows = []
		for option, details in self.options.items():
			default = self._format_default(details["default"])
			docstring = details["docstring"].replace("\n", " ")  # Remove any newlines in docstring
			row = f"{option:<{max_option_length}} | {default:<{max_default_length}} | {docstring}"
			rows.append(row)

		# Combine all parts
		table = "\n".join([header, separator, *rows])
		return f"ConfigRegistry:\n{table}"

	def _format_default(self, default: Any) -> str:
		if callable(default):
			return "<dynamic>"
		return str(default)


registry = ConfigRegistry()


def register(option: str, docstring: str, default: Any):
	"""Register a new configuration option with documentation and default value.

	Args:
	    option: Name of the configuration option
	    docstring: Documentation describing the option
	    default: Default value for the option
	"""
	registry.register(option, docstring, default)


# Global default config
register("redis_queue", "Redis URL for queue management", "redis://127.0.0.1:11311")
register("redis_cache", "Redis URL for caching", "redis://127.0.0.1:13311")
register("db_type", "Database type (mariadb or postgres)", "mariadb")
register("db_host", "Database host address", "127.0.0.1")
register("db_port", "Database port number", lambda c: 5432 if c.db_type == "postgres" else 3306)
register("db_user", "Database user name", lambda c: c.db_name)
register("db_name", "Database name", lambda c: c.db_user)
register("db_socket", "Unix socket file path for database connection (optional)", None)


class ConfigHandler:
	"""Handles loading, storing and updating configuration values from files and environment.

	Supports hot reloading of configuration upon tainting.
	"""

	def __init__(self, config_path: str):
		self.config_path = config_path
		self._config = None
		self.__config = None
		self._config_stale = True

	def taint(self):
		"Mark configuration as stale to trigger reload"
		self._config_stale = True

	@property
	def config(self) -> ConfigType:
		"Get current configuration, reloading if stale"
		if self._config is None or self._config_stale:
			if os.path.exists(self.config_path):
				with open(self.config_path) as f:
					self.__config = json.load(f)
			else:
				self.__config = {}
			self._config = ConfigType(**self.__config)
			self._update_from_env()
			self._apply_extra_config()
			# TODO: enable in-memory caching only once we have identified a mechanism to hot-reload on external config changes
			# self._config_stale = False
		return self._config

	def update_config(self, updates: dict[str, Any]):
		"""Update configuration with new values and save to config file.

		Args:
		    updates: Dictionary of configuration updates to apply

		Raises:
		    Timeout: If unable to acquire file lock for saving
		"""
		self.__config.update(updates)
		try:
			with FileLock(f"{self.config_path}.lock", timeout=5):
				with open(self.config_path, "w") as f:
					from frappe.utils.response import json_handler

					json.dump(self.__config, f, indent=2, default=json_handler, sort_keys=True)
		except Timeout as e:
			from frappe import log_error

			log_error(f"Filelock: Failed to aquire {self.config_path}.lock")
			raise e
		self._config_stale = True

	def _update_from_env(self):
		"Update config values from environment variables"
		for key in self._config.keys():
			# Convert camelCase or kebab-case to SNAKE_CASE
			env_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
			env_key = env_key.replace("-", "_")
			env_key = f"FRAPPE_{env_key.upper()}"
			if env_value := os.environ.get(env_key):
				self._config[key] = env_value

	def _apply_extra_config(self):
		"Apply additional configuration from external modules"
		# TODO: maybe motion to deprecate https://github.com/frappe/frappe/pull/24706#issuecomment-2471209484
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
