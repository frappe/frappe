import inspect
import typing
from collections.abc import Callable
from functools import lru_cache, wraps
from inspect import _empty, isclass
from types import EllipsisType
from typing import ForwardRef, Union
from unittest import mock

from pydantic import ConfigDict, PydanticUserError
from pydantic import TypeAdapter as PydanticTypeAdapter
from pydantic import ValidationError as PydanticValidationError

import frappe
from frappe.exceptions import FrappeTypeError

SLACK_DICT = {
	bool: bool | int | float,
}
ForwardRefOrStr = ForwardRef | str

FrappePydanticConfig = ConfigDict(arbitrary_types_allowed=True)


def validate_argument_types(
	func: Callable,
	apply_condition: Callable | None = None,
	force_types: bool | None = None,
):
	app = func.__module__.split(".")[0]
	_cached = None

	@wraps(func)
	def wrapper(*args, **kwargs):
		"""Validate argument types of whitelisted functions.

		:param args: Function arguments.
		:param kwargs: Function keyword arguments."""

		nonlocal force_types, _cached

		# Resolve it only once
		if force_types is None:
			force_types = any(frappe.get_hooks("require_type_annotated_api_methods", app_name=app))

		if apply_condition is None or apply_condition():
			if _cached is None:
				_cached = _precompute_validators(func, force_types)

			args, kwargs = _transform_args(func, args, kwargs, *_cached)

		return func(*args, **kwargs)

	return wrapper


def qualified_name(obj) -> str:
	"""
	Return the qualified name (e.g. package.module.Type) for the given object.

	Builtins and types from the :mod:typing package get special treatment by having the module
	name stripped from the generated name.

	"""
	discovered_type = obj if isclass(obj) else type(obj)
	module, qualname = discovered_type.__module__, discovered_type.__qualname__

	if module in {"typing", "types", "builtins"}:
		return qualname
	else:
		return f"{module}.{qualname}"


def raise_type_error(
	func: callable,
	arg_name: str,
	arg_type: type,
	arg_value: object,
	current_exception: Exception | None = None,
):
	"""
	Raise a TypeError with a message that includes the name of the argument, the expected type
	and the actual type of the value passed.

	"""
	module, qualname = func.__module__, func.__qualname__
	raise FrappeTypeError(
		f"Argument '{arg_name}' in '{module}.{qualname}' should be of type '{qualified_name(arg_type)}' but got "
		f"'{qualified_name(arg_value)}' instead."
	) from current_exception


@lru_cache(maxsize=2048)
def TypeAdapter(type_):
	try:
		return PydanticTypeAdapter(type_, config=FrappePydanticConfig)
	except PydanticUserError as e:
		# Cannot set config for types BaseModel, TypedDict and dataclass
		if e.code == "type-adapter-config-unused":
			return PydanticTypeAdapter(type_)

		raise e


def _resolve_annotations(func: Callable) -> dict:
	"""Resolve type annotations via get_type_hints, falling back to __annotations__.

	This correctly handles `from __future__ import annotations` (PEP 563),
	which stores all annotations as strings. get_type_hints evaluates them
	back into real type objects.

	If get_type_hints fails (e.g. TYPE_CHECKING imports, circular imports),
	we fall back to raw __annotations__. Unresolvable annotations (still str
	or ForwardRef) are skipped later in _precompute_validators.
	"""
	try:
		hints = typing.get_type_hints(func, include_extras=True)
	except Exception:
		hints = func.__annotations__.copy()

	hints.pop("return", None)
	return hints


def _build_effective_type(param_type, parameter: inspect.Parameter):
	"""Apply SLACK_DICT and default-value type widening to a parameter type."""
	if param_type in SLACK_DICT:
		param_type = SLACK_DICT[param_type]

	if parameter.default is not _empty and type(parameter.default) is not param_type:
		param_type = Union[param_type, type(parameter.default)]  # noqa: UP007

	return param_type


def _precompute_validators(func: Callable, force_types: bool = False):
	"""Resolve annotations and build TypeAdapters once per function."""
	annotations = _resolve_annotations(func)
	func_params = frappe._get_cached_signature_params(func)[0]

	param_validators = {}
	for idx, (param_name, parameter) in enumerate(func_params.items()):
		if idx == 0 and param_name in ("self", "cls"):
			continue
		if parameter.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
			continue

		if param_name not in annotations:
			if force_types:
				module, qualname = func.__module__, func.__qualname__
				raise FrappeTypeError(
					f"Argument '{param_name}' in '{module}.{qualname}' is missing type annotation. "
					f"All arguments must have type annotations when type checking is enforced."
				)
			continue

		param_type = annotations[param_name]

		# Skip types that still couldn't be resolved after get_type_hints
		if isinstance(param_type, ForwardRefOrStr):
			continue
		if any(isinstance(a, ForwardRefOrStr) for a in getattr(param_type, "__args__", ())):
			continue

		effective_type = _build_effective_type(param_type, parameter)
		param_validators[param_name] = TypeAdapter(effective_type)

	arg_index = {name: i for i, name in enumerate(func.__code__.co_varnames[: func.__code__.co_argcount])}

	return annotations, param_validators, arg_index


def _transform_args(
	func: Callable,
	args: tuple,
	kwargs: dict,
	annotations: dict,
	param_validators: dict,
	arg_index: dict,
):
	"""Validate and coerce argument types using precomputed validators."""
	if not (args or kwargs) or not param_validators:
		return args, kwargs

	new_args, new_kwargs = list(args), kwargs

	if args:
		prepared_args = dict(zip(arg_index, args, strict=False))
		if kwargs:
			prepared_args.update(kwargs)
	else:
		prepared_args = kwargs

	for param_name, adapter in param_validators.items():
		if param_name not in prepared_args:
			continue

		current_value = prepared_args[param_name]

		# ignore unittest.mock objects
		if isinstance(current_value, mock.Mock):
			continue

		try:
			validated = adapter.validate_python(current_value)
		except (TypeError, PydanticValidationError) as e:
			raise_type_error(func, param_name, annotations[param_name], current_value, current_exception=e)

		if isinstance(validated, EllipsisType):
			raise_type_error(func, param_name, annotations[param_name], current_value)

		if param_name in kwargs:
			new_kwargs[param_name] = validated
		elif param_name in arg_index:
			new_args[arg_index[param_name]] = validated

	return new_args, new_kwargs
