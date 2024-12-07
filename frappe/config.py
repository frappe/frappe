"""
This module provides a comprehensive configuration management system for the Frappe framework.
It includes classes and functions to register, load, store, and update configuration options
from various sources such as files, environment variables.

### Key Classes
- `ConfigType`: A dictionary subclass that provides attribute-style access to configuration options
  and warns when accessing unregistered configuration options.
- `ConfigRegistry`: A registry for configuration options with their documentation and default values.
- `ConfigHandler`: Handles loading, storing, and updating configuration values from files and environment.
  Supports hot reloading of configuration upon changes.

### Configuration Registry
The `ConfigRegistry` class allows registering configuration options with their documentation and default values.
This registry is used to manage and document all available configuration options.

### Configuration Handling
The `ConfigHandler` class is responsible for loading configuration from files, updating it from environment variables,
and applying additional configuration from external modules. It also supports hot reloading of the configuration.

### Example Usage
```python
from config_manager import register

# Register a new configuration option
register("new_option", "Documentation for the new option", "default_value")
```

### Notes
- Configuration options can be registered with default values that can be either static or dynamic (callable).
- Environment variables are used to override configuration values.
- Additional configuration can be applied from external modules using the `extra_config` option.
- The module uses file locking to ensure safe updates to the configuration file.

### Global Configuration
The module includes global default configurations for common Frappe settings such as Redis URLs, database connections,
and more. These can be overridden using environment variables or by updating the configuration file.
"""

import importlib
import json
import os
import pprint
import re
import traceback
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeAlias, TypedDict, cast

from filelock import FileLock, Timeout
from typing_extensions import NotRequired, override


class FrappeUnregisteredConfigOptionWarning(Warning):
	pass


ConfigValue: TypeAlias = str | bool | int | float | list["ConfigValue"] | dict[str, "ConfigValue"]
ConfigCallable: TypeAlias = Callable[["ConfigType"], ConfigValue | None]


class ConfigType(dict[str, ConfigValue]):
	"""A dictionary subclass that provides attribute-style access to configuration options.

	Warns when accessing unregistered configuration options.
	"""

	@override
	def __repr__(self) -> str:
		return pprint.pformat(dict(self), indent=2, width=80, sort_dicts=False)

	def __getattr__(self, name: str) -> ConfigValue | None:
		if name not in registry.options:
			# filter out noise in ipython console
			if not name.startswith("_ipython") and name != "_repr_mimebundle_":
				warnings.warn(
					f"Accessing unregistered configuration option: {name}",
					FrappeUnregisteredConfigOptionWarning,
					stacklevel=2,
				)
		if name not in self and (option := registry.options.get(name)) and (default := option["default"]):
			if callable(default):
				return default(self)
			return default
		elif name not in self:
			return None
		return self[name]


class ConfigRegistryOption(TypedDict):
	docstring: str
	default: NotRequired[ConfigCallable | ConfigValue | None]


class ConfigRegistry:
	"""Registry for configuration options with their documentation and default values."""

	def __init__(self):
		self.options: dict[str, ConfigRegistryOption] = {}

	def register(self, option: str, docstring: str, default: ConfigCallable | ConfigValue | None):
		self.options[option] = {"docstring": docstring, "default": default}

	@override
	def __repr__(self) -> str:
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

	def _format_default(self, default: ConfigCallable | ConfigValue | None) -> str:
		if callable(default):
			return "<dynamic>"
		return str(default)


registry = ConfigRegistry()


def register(option: str, docstring: str, default: ConfigCallable | ConfigValue | None):
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

	__config: dict[str, ConfigValue | None]
	_config: ConfigType
	_config_stale: bool

	def __init__(self, config_path: str | Path):
		self.config_path = Path(config_path)
		self._config_stale = True

	def taint(self):
		"Mark configuration as stale to trigger reload"
		self._config_stale = True

	@property
	def config(self) -> ConfigType:
		"Get current configuration, reloading if stale"
		if not hasattr(self, "_config") or self._config_stale:
			if self.config_path.exists():
				self.__config = json.loads(self.config_path.read_bytes())
			self._config = ConfigType(**self.__config)
			self._update_from_env()
			self._apply_extra_config()
			# TODO: enable in-memory caching only once we have identified a mechanism to hot-reload on external config changes
			# self._config_stale = False
		return self._config

	def update_config(self, updates: dict[str, ConfigValue | None]):
		"""Update configuration with new values and save to config file.

		Args:
		    updates: Dictionary of configuration updates to apply

		Raises:
		    Timeout: If unable to acquire file lock for saving
		"""
		self.__config.update(updates)
		try:
			with FileLock(f"{self.config_path}.lock", timeout=5):
				from frappe.utils.response import json_handler

				self.config_path.write_text(
					json.dumps(
						self.__config,
						indent=2,
						default=json_handler,  # type: ignore[no-any-expr]
						sort_keys=True,
					)
				)

		except Timeout as e:
			from frappe.utils.error import log_error

			log_error(f"Filelock: Failed to aquire {self.config_path}.lock")  # type: ignore[no-untyped-call]
			raise e
		self._config_stale = True

	def _update_from_env(self):
		"Update config values from environment variables"
		assert isinstance(self._config, ConfigType)  # will never be None by now
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
		assert isinstance(self._config, ConfigType)  # will never be None by now
		if extra_config := cast(str | list[str], self._config.get("extra_config")):
			if isinstance(extra_config, str):
				extra_config = [extra_config]
			for hook in extra_config:
				try:
					module, method = hook.rsplit(".", 1)
					self._config.update(getattr(importlib.import_module(module), method)())  # type: ignore[no-any-expr]
				except Exception:
					print(f"Config hook {hook} failed")
					traceback.print_exc()
