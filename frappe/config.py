import importlib
import os
import traceback
from typing import Any

import click

import frappe
from frappe import _dict, get_file_json
from frappe.exceptions import IncorrectSitePath
from frappe.utils.caching import site_cache


def get_site_config(
	sites_path: str | None = None,
	site_path: str | None = None,
	*,
	cached=False,
) -> _dict[str, Any]:
	"""Return `site_config.json` combined with `sites/common_site_config.json`.
	`site_config` is a set of site wide settings like database name, password, email etc.
	"""

	sites_path = sites_path or getattr(frappe.local, "sites_path", ".")
	site_path = site_path or getattr(frappe.local, "site_path", None)

	if cached:
		return _cached_get_site_config(sites_path, site_path).copy()
	else:
		return _get_site_config(sites_path, site_path)


def _get_site_config(sites_path: str, site_path: str) -> _dict[str, Any]:
	config: _dict[str, Any] = _dict()

	common_config = get_common_site_config(sites_path)

	if sites_path:
		config.update(common_config)

	if site_path:
		site_config = os.path.join(site_path, "site_config.json")
		if os.path.exists(site_config):
			try:
				config.update(get_file_json(site_config))
			except Exception as error:
				click.secho(f"{frappe.local.site}/site_config.json is invalid", fg="red")
				print(error)
				raise
		elif frappe.local.site and not frappe.local.flags.new_site:
			error_msg = f"{frappe.local.site} does not exist."
			if common_config.developer_mode:
				from frappe.utils import get_sites

				all_sites = get_sites()
				error_msg += "\n\nSites on this bench:\n"
				error_msg += "\n".join(f"* {site}" for site in all_sites)

			raise IncorrectSitePath(error_msg)

	# Generalized env variable overrides and defaults
	def db_default_ports(db_type):
		if db_type == "mariadb":
			from frappe.database.mariadb.database import MariaDBDatabase

			return MariaDBDatabase.default_port
		elif db_type == "postgres":
			from frappe.database.postgres.database import PostgresDatabase

			return PostgresDatabase.default_port

		raise ValueError(f"Unsupported db_type={db_type}")

	config["redis_queue"] = (
		os.environ.get("FRAPPE_REDIS_QUEUE") or config.get("redis_queue") or "redis://127.0.0.1:11311"
	)
	config["redis_cache"] = (
		os.environ.get("FRAPPE_REDIS_CACHE") or config.get("redis_cache") or "redis://127.0.0.1:13311"
	)
	config["db_type"] = os.environ.get("FRAPPE_DB_TYPE") or config.get("db_type") or "mariadb"

	if config["db_type"] in ("mariadb", "postgres"):
		config["db_socket"] = os.environ.get("FRAPPE_DB_SOCKET") or config.get("db_socket")
		config["db_host"] = os.environ.get("FRAPPE_DB_HOST") or config.get("db_host") or "127.0.0.1"
		config["db_port"] = int(
			os.environ.get("FRAPPE_DB_PORT") or config.get("db_port") or db_default_ports(config["db_type"])
		)

		# Set the user as database name if not set in config
		config["db_user"] = os.environ.get("FRAPPE_DB_USER") or config.get("db_user") or config.get("db_name")

		# read password
		config["db_password"] = os.environ.get("FRAPPE_DB_PASSWORD") or config.get("db_password")

	# vice versa for dbname if not defined
	config["db_name"] = os.environ.get("FRAPPE_DB_NAME") or config.get("db_name") or config["db_user"]

	# Allow externally extending the config with hooks
	if extra_config := config.get("extra_config"):
		if isinstance(extra_config, str):
			extra_config = [extra_config]
		for hook in extra_config:
			try:
				module, method = hook.rsplit(".", 1)
				config |= getattr(importlib.import_module(module), method)()
			except Exception:
				print(f"Config hook {hook} failed")
				traceback.print_exc()

	return config


def get_common_site_config(sites_path: str | None = None, cached=False) -> _dict[str, Any]:
	"""Return common site config as dictionary.

	This is useful for:
	- checking configuration which should only be allowed in common site config
	- When no site context is present and fallback is required.
	"""
	sites_path = sites_path or getattr(frappe.local, "sites_path", ".")
	if cached:
		return _cached_get_common_site_config(sites_path).copy()
	else:
		return _get_common_site_config(sites_path)


def _get_common_site_config(sites_path: str) -> _dict[str, Any]:
	common_site_config = os.path.join(sites_path, "common_site_config.json")
	if os.path.exists(common_site_config):
		try:
			return _dict(get_file_json(common_site_config))
		except Exception as error:
			click.secho("common_site_config.json is invalid", fg="red")
			print(error)
			raise
	return _dict()


# These variants cache the values in *memory* for repeat access, use it in web requests or anywhere
# else it helps to avoid recurring accesses in *long-lived* processes.
_cached_get_site_config = site_cache(ttl=60, maxsize=16)(_get_site_config)
_cached_get_common_site_config = site_cache(ttl=60, maxsize=16)(_get_common_site_config)


def clear_site_config_cache():
	_cached_get_common_site_config.clear_cache()
	_cached_get_site_config.clear_cache()


def get_conf(site: str | None = None) -> _dict[str, Any]:
	if hasattr(frappe.local, "conf"):
		return frappe.local.conf

	# if no site, get from common_site_config.json
	with frappe.init_site(site):
		return frappe.local.conf
