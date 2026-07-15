"""Native discovery documents for API clients."""

import ast
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.model.base_document import get_controller

CACHE_TTL = 60 * 60
DISCOVERY_CACHE_PREFIX = "api:v2:discovery"
PYTHON_METHOD_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:python"
PYTHON_SEARCH_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:python_search"
DOCTYPE_METHOD_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:doctype_nonstandard"
DOCTYPE_SEARCH_CACHE_KEY = f"{DISCOVERY_CACHE_PREFIX}:global:methods:doctype_nonstandard_search"
DISCOVERY_BUILD_JOB_ID = "api-v2-discovery-build"


class DiscoveryCacheUnavailable(frappe.ValidationError):
	http_status_code = 503
	skip_error_log = True


def root() -> dict[str, Any]:
	frappe.only_for("System Manager")
	method_index = _method_index()
	doctype_method_index = _doctype_method_index()
	return {
		"type": "discovery",
		"resources": {"methods": len(method_index), "doctype_methods": len(doctype_method_index)},
		"links": {
			"self": "/api/v2/discovery",
			"search": "/api/v2/discovery/search?q={query}",
			"methods": "/api/v2/discovery/method",
			"method": "/api/v2/discovery/method/{method}",
			"doctype_methods": "/api/v2/discovery/doctype/{doctype}",
			"doctype_method": "/api/v2/discovery/doctype/{doctype}/method/{method}",
		},
	}


def search(q: str | None = None) -> dict[str, Any]:
	frappe.only_for("System Manager")
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
	frappe.only_for("System Manager")
	return {"type": "method_index", "methods": _method_index()}


def method(method: str) -> dict[str, Any]:
	frappe.only_for("System Manager")
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
			"kind": "rpc",
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


def doctype_methods(doctype: str) -> dict[str, Any]:
	frappe.only_for("System Manager")
	methods = [
		_doctype_method_summary(doctype, name, fn)
		for name, fn, _defining_class in _get_doctype_methods(doctype)
	]
	return {"type": "method_index", "doctype": doctype, "methods": methods}


def doctype_method(doctype: str, method: str) -> dict[str, Any]:
	frappe.only_for("System Manager")
	for name, fn, defining_class in _get_doctype_methods(doctype):
		if name == method:
			return _doctype_method_document(doctype, name, fn, defining_class)

	frappe.throw(
		_("Method {0} is not available for discovery on DocType {1}").format(method, doctype),
		frappe.DoesNotExistError,
	)


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

	doctype_items = []
	doctype_search_entries = []
	for doctype, method_name, fn, _defining_class in _discover_doctype_methods():
		method = _doctype_method_summary(doctype, method_name, fn)
		doctype_items.append(method)
		doctype_search_entries.append(
			{
				"method": method,
				"haystack": _method_search_text(method, inspect.getdoc(fn)),
			}
		)

	frappe.cache.set_value(DOCTYPE_METHOD_CACHE_KEY, doctype_items, expires_in_sec=CACHE_TTL)
	frappe.cache.set_value(DOCTYPE_SEARCH_CACHE_KEY, doctype_search_entries, expires_in_sec=CACHE_TTL)


def _search_index() -> list[tuple[dict[str, Any], str]]:
	entries: list[tuple[dict[str, Any], str]] = []
	for item in _get_cached_python_search_entries():
		method = item["method"]
		entry = _without_none({"type": "method", **method, "kind": "rpc"})
		entries.append((entry, f"{item['haystack']} rpc"))

	for path, _script in _visible_server_scripts():
		entry = {"type": "method", "kind": "rpc", "path": path}
		entries.append((entry, _method_search_text(entry)))

	for item in _get_cached_doctype_search_entries():
		entry = _without_none({**item["method"], "kind": "doctype"})
		entries.append((entry, f"{item['haystack']} doctype"))

	return sorted(
		entries,
		key=lambda item: (
			item[0].get("path") or "",
			item[0].get("doctype") or "",
			item[0].get("method") or "",
		),
	)


def _method_search_text(entry: dict[str, Any], docstring: str | None = None) -> str:
	return " ".join(
		str(value or "")
		for value in (
			entry.get("type"),
			entry.get("kind"),
			entry.get("path"),
			entry.get("doctype"),
			entry.get("method"),
			entry.get("description"),
			docstring,
		)
	).lower()


def _method_index() -> list[dict[str, Any]]:
	items = [{**item, "kind": "rpc"} for item in _get_cached_python_methods()]
	items.extend({"kind": "rpc", "path": path} for path, _script in _visible_server_scripts())
	items.extend({**item, "kind": "doctype"} for item in _doctype_method_index())
	return sorted(
		items,
		key=lambda item: (
			item.get("path") or "",
			item.get("doctype") or "",
			item.get("method") or "",
		),
	)


def _doctype_method_index() -> list[dict[str, Any]]:
	return _get_required_cache_value(DOCTYPE_METHOD_CACHE_KEY)


def _get_cached_python_methods() -> list[dict[str, Any]]:
	return _get_required_cache_value(PYTHON_METHOD_CACHE_KEY)


def _get_cached_python_search_entries() -> list[dict[str, Any]]:
	return _get_required_cache_value(PYTHON_SEARCH_CACHE_KEY)


def _get_cached_doctype_search_entries() -> list[dict[str, Any]]:
	return _get_required_cache_value(DOCTYPE_SEARCH_CACHE_KEY)


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
			"kind": "rpc",
			"path": f"{fn.__module__}.{fn.__name__}",
			"description": docstring.splitlines()[0] if docstring else None,
		}
	)


def _method_document(path: str, fn: Callable) -> dict[str, Any]:
	return _without_none(
		{
			"type": "method",
			"kind": "rpc",
			"path": path,
			"name": fn.__name__,
			"http_methods": frappe.allowed_http_methods_for_whitelisted_func.get(fn, []),
			"allow_guest": fn in frappe.guest_methods,
			"params": _method_params(fn),
			"endpoint": f"/api/v2/method/{path}",
			"docstring": inspect.getdoc(fn),
			"source": _method_source(fn),
		}
	)


def _doctype_method_summary(
	doctype: str,
	method: str,
	fn: Callable,
) -> dict[str, Any]:
	docstring = inspect.getdoc(fn)
	return _without_none(
		{
			"type": "method",
			"kind": "doctype",
			"doctype": doctype,
			"method": method,
			"description": docstring.splitlines()[0] if docstring else None,
		}
	)


def _doctype_method_document(doctype: str, method: str, fn: Callable, defining_class: type) -> dict[str, Any]:
	http_methods = [
		method
		for method in frappe.allowed_http_methods_for_whitelisted_func.get(fn, ())
		if method in {"GET", "POST"}
	]
	return _without_none(
		{
			"type": "method",
			"kind": "doctype",
			"doctype": doctype,
			"method": method,
			"defined_in": _class_path(defining_class),
			"endpoint": f"/api/v2/document/{doctype}/{{name}}/method/{method}",
			"http_methods": http_methods,
			"permission": {"GET": "read", "POST": "write"},
			"params": _method_params(fn),
			"docstring": inspect.getdoc(fn),
			"source": _method_source(fn),
		}
	)


def _class_path(class_: type) -> str:
	return f"{class_.__module__}.{class_.__name__}"


def _method_source(fn: Callable) -> str | None:
	"""Return the method's source code, but only if its app opts in.

	Exposing source is safe for open source apps and helps API clients (e.g. AI
	agents) understand what a method does. Apps must explicitly opt in via the
	`expose_discovery_source` hook, since a closed source app may not want its
	implementation leaked over the API.
	"""
	app = fn.__module__.split(".", 1)[0]
	if not any(frappe.get_hooks("expose_discovery_source", app_name=app)):
		return None

	try:
		return inspect.getsource(fn)
	except (OSError, TypeError):
		return None


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


def _discover_doctype_methods() -> list[tuple[str, str, Callable, type]]:
	methods = []
	doctypes = frappe.get_all(
		"DocType",
		filters={"istable": 0},
		pluck="name",
		order_by="name",
	)
	for doctype in doctypes:
		try:
			doctype_methods = _get_doctype_methods(doctype)
		except Exception:
			continue
		methods.extend(
			(doctype, method_name, fn, defining_class)
			for method_name, fn, defining_class in doctype_methods
			if not _is_standard_doctype_method(defining_class)
		)

	return methods


def _get_doctype_methods(doctype: str) -> list[tuple[str, Callable, type]]:
	meta = frappe.get_meta(doctype)
	if meta.istable:
		frappe.throw(
			_("DocType {0} is not available for discovery").format(doctype), frappe.DoesNotExistError
		)

	controller = get_controller(doctype)
	methods = []
	for method_name in dir(controller):
		defining_class = _defining_class(controller, method_name)
		if not defining_class:
			continue
		try:
			fn = _unwrap_method(getattr(controller, method_name))
		except (AttributeError, TypeError):
			continue
		if not callable(fn):
			continue
		if fn not in frappe.whitelisted or not _doctype_method_applies(meta, method_name):
			continue
		methods.append((method_name, fn, defining_class))

	return methods


def _unwrap_method(method: Any) -> Any:
	return getattr(method, "__func__", method)


def _defining_class(controller: type, method: str) -> type | None:
	return next((class_ for class_ in inspect.getmro(controller) if method in class_.__dict__), None)


def _is_standard_doctype_method(defining_class: type) -> bool:
	return _class_path(defining_class) == "frappe.model.document.Document"


def _doctype_method_applies(meta: Any, method: str) -> bool:
	if method in {"submit", "cancel", "discard"} and not meta.is_submittable:
		return False
	if method == "rename" and not meta.allow_rename:
		return False
	return True


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
