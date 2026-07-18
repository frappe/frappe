# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Machinery for the `@frappe.public` decorator.

`@frappe.public` marks a whitelisted endpoint as an intentionally public,
stable API. It is purely declarative: it never changes runtime behavior
(auth, serialization, rate limits). It enforces a structural contract at
import time (type annotations + docstring) and attaches machine-readable
metadata used by discovery and OpenAPI tooling.

Usage::

	@frappe.public(group="Documents")
	@frappe.whitelist(methods=["POST"])
	def submit(doc: dict) -> dict:
		\"""Submit a submittable document.

		:param doc: Document dict, must include doctype and name.
		:return: The submitted document as a dict.
		\"""
"""

import inspect
import os
import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import frappe

__all__ = [
	"PublicAPIContractError",
	"PublicAPISpec",
	"get_public_spec",
	"iter_public_apis",
	"public",
]


class PublicAPIContractError(TypeError):
	"""A function marked `@frappe.public` does not satisfy the public API contract."""


@dataclass(frozen=True)
class PublicAPISpec:
	"""Metadata declared on a public API via `@frappe.public`.

	Only *declared* metadata lives here. Everything derivable — canonical
	dotted path, allowed HTTP methods, guest access, signature, parsed
	docstring — is computed at read time from the function itself.
	"""

	group: str | None = None
	deprecated: str | None = None


def public(*, group: str | None = None, deprecated: str | None = None) -> Callable:
	"""Mark a whitelisted function as an intentionally public, stable API.

	Must be stacked on top of `@frappe.whitelist` — whitelist is exposure,
	public is contract. Validates that the function has full type annotations
	and a docstring, then attaches a `PublicAPISpec` as `__public_api__` and
	returns the same function object (never a wrapper).

	Contract violations raise `PublicAPIContractError` in developer mode,
	tests, and CI; in production they only warn, so a non-compliant
	third-party app cannot take a site down.

	:param group: Logical grouping for discovery / OpenAPI tag, e.g. "Documents".
	:param deprecated: Deprecation note with version and replacement,
		e.g. "v17: use frappe.client.bulk_update".
	"""

	def marker(fn: Callable) -> Callable:
		_check_public_contract(fn)
		fn.__public_api__ = PublicAPISpec(group=group, deprecated=deprecated)  # type: ignore[attr-defined]
		return fn

	return marker


def get_public_spec(fn: Callable) -> PublicAPISpec | None:
	"""Return the `PublicAPISpec` for a function, or None if it isn't `@public`.

	`functools.wraps` copies `__public_api__` onto wrappers, so a plain
	attribute lookup usually suffices; walking the `__wrapped__` chain is a
	defensive fallback for non-conforming wrappers.
	"""
	seen = set()
	current: Callable | None = fn
	while current is not None and id(current) not in seen:
		if spec := getattr(current, "__public_api__", None):
			return spec
		seen.add(id(current))
		current = getattr(current, "__wrapped__", None)
	return None


def iter_public_apis() -> Iterator[tuple[Callable, PublicAPISpec]]:
	"""Yield (function, spec) for every `@frappe.public` API registered so far.

	Only functions whose defining module has been imported appear here — same
	semantics as `frappe.whitelisted` itself.
	"""
	for fn in frappe.whitelisted:
		if spec := get_public_spec(fn):
			yield fn, spec


def _check_public_contract(fn: Callable) -> None:
	problems = _find_contract_violations(fn)
	if not problems:
		return

	fn_path = f"{fn.__module__}.{getattr(fn, '__qualname__', fn.__name__)}"
	details = "\n".join(f"  - {problem}" for problem in problems)
	message = f"@frappe.public applied to {fn_path} but the public API contract is not met:\n{details}"

	if _strict_contract_enforcement():
		raise PublicAPIContractError(message)
	warnings.warn(message, stacklevel=4)


def _find_contract_violations(fn: Callable) -> list[str]:
	problems = []

	if fn not in frappe.whitelisted:
		problems.append(
			"function is not whitelisted; apply @frappe.public above @frappe.whitelist:\n"
			"      @frappe.public(...)\n"
			"      @frappe.whitelist(...)\n"
			"      def endpoint(...): ..."
		)

	try:
		signature = inspect.signature(fn)
	except (TypeError, ValueError):
		problems.append("could not inspect the function signature")
		return problems

	for name, parameter in signature.parameters.items():
		if name in ("self", "cls"):
			continue
		if parameter.annotation is inspect.Parameter.empty:
			problems.append(f"parameter {name!r} is missing a type annotation")

	if signature.return_annotation is inspect.Signature.empty:
		problems.append("return type is not annotated (annotate '-> None' explicitly if nothing is returned)")

	if not (inspect.getdoc(fn) or "").strip():
		problems.append("docstring is missing or empty")

	return problems


def _strict_contract_enforcement() -> bool:
	"""Hard-fail in developer mode, tests, and CI; warn otherwise (production)."""
	return bool(frappe.in_test or frappe._dev_server or os.environ.get("CI"))
