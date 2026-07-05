"""Native discovery documents for API clients."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map

CACHE_TTL = 5 * 60
DISCOVERY_CACHE_PREFIX = "api:v2:discovery"
PYTHON_METHOD_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:python"
PYTHON_SEARCH_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:python_search"
SERVER_SCRIPT_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:server_scripts"
DISCOVERY_BUILD_JOB_ID = "api-v2-discovery-build"


class DiscoveryCacheUnavailable(frappe.ValidationError):
	http_status_code = 503


def root() -> dict[str, Any]:
	method_index = _method_index()
	return {
		"type": "discovery",
		"resources": {"methods": len(method_index)},
		"links": {
			"self": "/api/v2/discovery",
			"search": "/api/v2/discovery/search?q={query}",
			"methods": "/api/v2/discovery/method",
			"method": "/api/v2/discovery/method/{method}",
		},
	}


def search(q: str | None = None) -> dict[str, Any]:
	query = (q or "").strip().lower()
	index = _search_index()
	entries = [entry for entry, _haystack in index]
	if not query:
		return {"query": q or "", "results": entries[:50]}

	tokens = [token for token in query.split() if token]
	matches = []
	for entry, haystack in index:
		if all(token in haystack for token in tokens):
			matches.append(entry)

	return {"query": q or "", "results": matches[:50]}


def methods() -> dict[str, Any]:
	return {"type": "method_index", "methods": _method_index()}


def method(method: str) -> dict[str, Any]:
	method = frappe.override_whitelisted_method(method)
	server_script = _api_server_scripts().get(method)
	if server_script:
		if not frappe.has_permission("Server Script", "read"):
			frappe.throw(
				_("Method {0} is not available for discovery").format(method), frappe.PermissionError
			)
		return _server_script_method_document(method, server_script)

	fn = _get_whitelisted_method(method)
	if not fn:
		frappe.throw(_("Method {0} is not available for discovery").format(method), frappe.DoesNotExistError)

	return _method_document(method, fn)


def clear_cache(user: str | None = None):
	frappe.cache.delete_keys(f"{DISCOVERY_CACHE_PREFIX}:")


def build_cache() -> None:
	"""Build API discovery cache from source in a background job."""
	_build_python_method_cache()
	_build_api_server_scripts_cache()


def _search_index() -> list[tuple[dict[str, Any], str]]:
	entries: list[tuple[dict[str, Any], str]] = []
	for item in _get_cached_python_search_entries():
		method = item["method"]
		if not _method_summary_visible_to_user(method):
			continue
		entry = _without_none({"type": "method", **method})
		entries.append((entry, item["haystack"]))

	for path, _script in _visible_server_scripts():
		entry = {"type": "method", "path": path}
		entries.append((entry, _method_search_text(entry)))

	return sorted(entries, key=lambda item: item[0].get("path") or "")


def _method_search_text(entry: dict[str, Any], docstring: str | None = None) -> str:
	return " ".join(
		str(value or "")
		for value in (entry.get("type"), entry.get("path"), entry.get("description"), docstring)
	).lower()


def _method_index() -> list[dict[str, Any]]:
	items = [method for method in _get_cached_python_methods() if _method_summary_visible_to_user(method)]
	items.extend({"path": path} for path, _script in _visible_server_scripts())
	return sorted(items, key=lambda item: item["path"])


def _get_cached_python_methods() -> list[dict[str, Any]]:
	return _get_required_cache_value(PYTHON_METHOD_CACHE_KEY)


def _get_cached_python_search_entries() -> list[dict[str, Any]]:
	return _get_required_cache_value(PYTHON_SEARCH_CACHE_KEY)


def _get_required_cache_value(key: str) -> Any:
	value = frappe.cache.get_value(key, expires=True)
	if value is None:
		_trigger_cache_build()
		frappe.throw(
			_("API discovery cache is being generated. Please try again in a few seconds."),
			DiscoveryCacheUnavailable,
		)
	return value


def _trigger_cache_build() -> None:
	from frappe.utils.background_jobs import is_job_enqueued

	if is_job_enqueued(DISCOVERY_BUILD_JOB_ID):
		return

	frappe.enqueue(
		"frappe.api.discovery.build_cache",
		queue="long",
		job_id=DISCOVERY_BUILD_JOB_ID,
		deduplicate=True,
	)


def _build_python_method_cache() -> list[dict[str, Any]]:
	items = []
	search_entries = []
	for path in _discover_whitelisted_method_paths():
		if fn := _get_whitelisted_method(path, ignore_cache=True):
			method = _method_summary(fn)
			items.append(method)
			entry = {"type": "method", **method}
			search_entries.append(
				{"method": method, "haystack": _method_search_text(entry, inspect.getdoc(fn))}
			)

	frappe.cache.set_value(PYTHON_METHOD_CACHE_KEY, items, expires_in_sec=CACHE_TTL)
	frappe.cache.set_value(PYTHON_SEARCH_CACHE_KEY, search_entries, expires_in_sec=CACHE_TTL)
	return items


def _method_summary_visible_to_user(method: dict[str, Any]) -> bool:
	return frappe.session.user != "Guest" or bool(method.get("allow_guest"))


def _method_summary(fn: Callable) -> dict[str, Any]:
	return _without_none(
		{
			"path": f"{fn.__module__}.{fn.__name__}",
			"allow_guest": fn in frappe.guest_methods,
			"description": _first_docstring_line(fn),
		}
	)


def _method_document(path: str, fn: Callable) -> dict[str, Any]:
	return _without_none(
		{
			"type": "method",
			"path": path,
			"name": fn.__name__,
			"http_methods": frappe.allowed_http_methods_for_whitelisted_func.get(fn, []),
			"allow_guest": fn in frappe.guest_methods,
			"params": _method_params(fn),
			"endpoint": f"/api/v2/method/{path}",
			"docstring": inspect.getdoc(fn),
		}
	)


def _server_script_method_document(path: str, script: str) -> dict[str, Any]:
	return {
		"type": "method",
		"path": path,
		"name": script,
		"http_methods": ["GET", "POST", "PUT", "DELETE"],
		"params": [],
		"endpoint": f"/api/v2/method/{path}",
	}


def _visible_server_scripts() -> list[tuple[str, str]]:
	if not frappe.has_permission("Server Script", "read"):
		return []
	return sorted(_api_server_scripts().items())


def _api_server_scripts() -> dict[str, str]:
	return _get_required_cache_value(SERVER_SCRIPT_CACHE_KEY)


def _build_api_server_scripts_cache() -> dict[str, str]:
	scripts = {
		path: script
		for path, script in get_server_script_map().get("_api", {}).items()
		if isinstance(path, str) and path
	}
	frappe.cache.set_value(SERVER_SCRIPT_CACHE_KEY, scripts, expires_in_sec=CACHE_TTL)
	return scripts


def _get_whitelisted_method(path: str, ignore_cache: bool = False) -> Callable | None:
	if not ignore_cache and path not in {method["path"] for method in _get_cached_python_methods()}:
		return None

	try:
		fn = frappe.get_attr(path)
	except Exception:
		return None
	if ignore_cache and fn in frappe.whitelisted:
		return fn
	if not ignore_cache and _method_visible_to_user(fn):
		return fn
	return None


def _method_visible_to_user(fn: Callable) -> bool:
	if fn not in frappe.whitelisted:
		return False
	if frappe.session.user == "Guest" and fn not in frappe.guest_methods:
		return False
	return True


def _first_docstring_line(fn: Callable) -> str | None:
	docstring = inspect.getdoc(fn)
	if not docstring:
		return None
	return docstring.splitlines()[0]


def _discover_whitelisted_method_paths() -> list[str]:
	methods = set()
	for app in frappe.get_installed_apps(_ensure_on_bench=True):
		app_path = Path(frappe.get_app_path(app))
		if not app_path.exists():
			continue

		for file_path in app_path.rglob("*.py"):
			if _should_skip_python_file(file_path):
				continue

			module = _module_path_from_file(app, app_path, file_path)
			for method in _get_module_level_whitelisted_functions(file_path):
				methods.add(f"{module}.{method}")

	return sorted(methods)


def _should_skip_python_file(file_path: Path) -> bool:
	if frappe.in_test:
		return False
	return file_path.name.startswith("test_") or "tests" in file_path.parts


def _module_path_from_file(app: str, app_path: Path, file_path: Path) -> str:
	relative_path = file_path.relative_to(app_path).with_suffix("")
	parts = relative_path.parts[:-1] if relative_path.name == "__init__" else relative_path.parts
	return ".".join((app, *parts))


def _get_module_level_whitelisted_functions(file_path: Path) -> list[str]:
	try:
		tree = ast.parse(file_path.read_text(), filename=str(file_path))
	except (OSError, SyntaxError):
		return []

	methods = []
	for node in tree.body:
		if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _has_whitelist_decorator(node):
			methods.append(node.name)

	return methods


def _has_whitelist_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
	for decorator in node.decorator_list:
		decorator_func = decorator.func if isinstance(decorator, ast.Call) else decorator
		if _is_whitelist_decorator(decorator_func):
			return True

	return False


def _is_whitelist_decorator(decorator: ast.expr) -> bool:
	if isinstance(decorator, ast.Attribute):
		return (
			decorator.attr == "whitelist"
			and isinstance(decorator.value, ast.Name)
			and decorator.value.id == "frappe"
		)

	return isinstance(decorator, ast.Name) and decorator.id in {"whitelist", "whitelist_for_tests"}


def _method_params(fn: Callable) -> list[dict[str, Any]]:
	try:
		signature = inspect.signature(fn)
	except (TypeError, ValueError):
		return []

	params = []
	for name, parameter in signature.parameters.items():
		if name in {"self", "cls"}:
			continue
		params.append(
			_without_none(
				{
					"name": name,
					"required": parameter.default is inspect.Parameter.empty,
					"default": _jsonable_default(parameter.default),
					"type": _annotation_name(parameter.annotation),
				}
			)
		)
	return params


def _annotation_name(annotation: Any) -> str | None:
	if annotation is inspect.Parameter.empty:
		return None
	if isinstance(annotation, str):
		return annotation
	return inspect.formatannotation(annotation)


def _jsonable_default(default: Any) -> Any:
	if default is inspect.Parameter.empty:
		return None
	if isinstance(default, str | int | float | bool | list | tuple | dict) or default is None:
		return default
	return repr(default)


def _without_none(data: dict[str, Any]) -> dict[str, Any]:
	return {key: value for key, value in data.items() if value is not None}
