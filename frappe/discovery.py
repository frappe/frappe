# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Discovery of the public API surface declared via `@frappe.public`."""

import inspect

import frappe
from frappe.public_api import PublicAPISpec, iter_public_apis, public


def describe_public_api(fn, spec: PublicAPISpec) -> dict:
	"""Build the machine-readable description of one public API function."""
	signature = inspect.signature(fn)
	doc = inspect.getdoc(fn) or ""
	summary = doc.splitlines()[0] if doc else ""

	parameters = []
	for name, parameter in signature.parameters.items():
		if name in ("self", "cls"):
			continue
		param = {"name": name}
		if parameter.annotation is not inspect.Parameter.empty:
			param["type"] = inspect.formatannotation(parameter.annotation)
		if parameter.default is not inspect.Parameter.empty:
			param["default"] = repr(parameter.default)
		if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
			param["variadic"] = "args"
		elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
			param["variadic"] = "kwargs"
		parameters.append(param)

	description = {
		"path": f"{fn.__module__}.{fn.__qualname__}",
		"summary": summary,
		"group": spec.group,
		"methods": list(frappe.allowed_http_methods_for_whitelisted_func.get(fn, ())),
		"allow_guest": fn in frappe.guest_methods,
		"parameters": parameters,
	}
	if signature.return_annotation is not inspect.Signature.empty:
		description["return_type"] = inspect.formatannotation(signature.return_annotation)
	if spec.deprecated:
		description["deprecated"] = spec.deprecated

	return description


@public(group="Discovery")
@frappe.whitelist(methods=["GET"])
def get_public_apis() -> list[dict]:
	"""List the public APIs of all installed apps, with their signatures.

	Only endpoints explicitly marked `@frappe.public` appear here; each entry
	documents the canonical dotted path (`/api/method/<path>`), allowed HTTP
	methods, guest access, parameters and grouping.

	:return: One description dict per public API, sorted by group and path.
	"""
	_import_public_api_modules()
	apis = [describe_public_api(fn, spec) for fn, spec in iter_public_apis()]
	return sorted(apis, key=lambda d: (d["group"] or "", d["path"]))


def _import_public_api_modules():
	"""Import the modules registered via the `public_api_modules` hook.

	`@frappe.public` registers on import, so the registry is only complete
	once every module declaring public APIs has been imported in this process.
	"""
	for module in frappe.get_hooks("public_api_modules"):
		frappe.get_module(module)
