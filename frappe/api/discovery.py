"""Native discovery documents for API clients."""

import ast
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map

CACHE_TTL = 60 * 60
DISCOVERY_CACHE_PREFIX = "api:v2:discovery"
PYTHON_METHOD_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:python"
PYTHON_SEARCH_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:python_search"
DISCOVERY_BUILD_JOB_ID = "api-v2-discovery-build"


class DiscoveryCacheUnavailable(frappe.ValidationError):
	http_status_code = 503
	skip_error_log = True


def root() -> dict[str, Any]:
	frappe.only_for("Developer")
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
	frappe.only_for("Developer")
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
	frappe.only_for("Developer")
	return {"type": "method_index", "methods": _method_index()}


def method(method: str) -> dict[str, Any]:
	frappe.only_for("Developer")
	method = frappe.override_whitelisted_method(method)
	server_script = {
		path: script
		for path, script in get_server_script_map().get("_api", {}).items()
		if isinstance(path, str) and path
	}.get(method)
	if server_script:
		if not frappe.has_permission("Server Script", "read"):
			frappe.throw(
				_("Method {0} is not available for discovery").format(method), frappe.PermissionError
			)
		return {
			"type": "method",
			"path": method,
			"name": server_script,
			"http_methods": ["GET", "POST", "PUT", "DELETE"],
			"params": [],
			"endpoint": f"/api/v2/method/{method}",
		}

	fn = _get_whitelisted_method(method)
	if not fn:
		frappe.throw(_("Method {0} is not available for discovery").format(method), frappe.DoesNotExistError)

	return _method_document(method, fn)


def clear_cache(user: str | None = None):
	frappe.cache.delete_keys(f"{DISCOVERY_CACHE_PREFIX}:")


def build_cache() -> None:
	"""Build API discovery cache from source in a background job."""
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


def _search_index() -> list[tuple[dict[str, Any], str]]:
	entries: list[tuple[dict[str, Any], str]] = []
	for item in _get_cached_python_search_entries():
		method = item["method"]
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
	items = list(_get_cached_python_methods())
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
	frappe.enqueue(
		"frappe.api.discovery.build_cache",
		queue="long",
		job_id=DISCOVERY_BUILD_JOB_ID,
		deduplicate=True,
	)


def _method_summary(fn: Callable) -> dict[str, Any]:
	docstring = inspect.getdoc(fn)
	return _without_none(
		{
			"path": f"{fn.__module__}.{fn.__name__}",
			"allow_guest": fn in frappe.guest_methods,
			"description": docstring.splitlines()[0] if docstring else None,
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


def _visible_server_scripts() -> list[tuple[str, str]]:
	if not frappe.has_permission("Server Script", "read"):
		return []
	return sorted(
		(path, script)
		for path, script in get_server_script_map().get("_api", {}).items()
		if isinstance(path, str) and path
	)


def _get_whitelisted_method(path: str, ignore_cache: bool = False) -> Callable | None:
	if not ignore_cache and path not in {method["path"] for method in _get_cached_python_methods()}:
		return None

	try:
		fn = frappe.get_attr(path)
	except Exception:
		return None
	if ignore_cache and fn in frappe.whitelisted:
		return fn
	if not ignore_cache and fn in frappe.whitelisted:
		return fn
	return None


def _discover_whitelisted_method_paths() -> list[str]:
	methods = set()
	for app in frappe.get_installed_apps(_ensure_on_bench=True):
		app_path = Path(frappe.get_app_path(app))
		if not app_path.exists():
			continue

		for file_path in app_path.rglob("*.py"):
			if not frappe.in_test and file_path.name.startswith("test_"):
				continue

			module = _module_path_from_file(app, app_path, file_path)
			for method in _get_module_level_whitelisted_functions(file_path):
				methods.add(f"{module}.{method}")

	return sorted(methods)


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
