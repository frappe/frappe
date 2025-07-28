from collections.abc import Callable
from functools import lru_cache, wraps
from inspect import _empty, isclass
from types import EllipsisType
from typing import ForwardRef, TypeVar, Union
from unittest import mock

from pydantic import ConfigDict, PydanticUserError
from pydantic import TypeAdapter as PydanticTypeAdapter
from pydantic import ValidationError as PydanticValidationError

import frappe
from frappe.exceptions import FrappeTypeError

SLACK_DICT = {
	bool: (int, bool, float),
}
T = TypeVar("T")
ForwardRefOrStr = ForwardRef | str


FrappePydanticConfig = ConfigDict(arbitrary_types_allowed=True)


def validate_argument_types(func: Callable, apply_condition: Callable | None = None):
	@wraps(func)
	def wrapper(*args, **kwargs):
		"""Validate argument types of whitelisted functions.

		:param args: Function arguments.
		:param kwargs: Function keyword arguments."""

		if apply_condition is None or apply_condition():
			args, kwargs = transform_parameter_types(func, args, kwargs)

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

	if module in {"typing", "types"}:
		return obj
	elif module in {"builtins"}:
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


def transform_parameter_types(func: Callable, args: tuple, kwargs: dict):
	"""
	Validate the types of the arguments passed to a function with the type annotations
	defined on the function.
	"""

	annotations = func.__annotations__

	if (
		not (args or kwargs)
		or not annotations
		# No input validations to perform
		or (len(annotations) == 1 and "return" in annotations)
	):
		return args, kwargs

	new_args, new_kwargs = list(args), kwargs

	if args:
		# generate kwargs dict from args
		arg_names = func.__code__.co_varnames[: func.__code__.co_argcount]
		prepared_args = dict(zip(arg_names, args, strict=False))

		if kwargs:
			# update prepared_args with kwargs
			prepared_args.update(kwargs)

	else:
		prepared_args = kwargs

	# check if type hints dont match the default values
	func_params = frappe._get_cached_signature_params(func)[0]

	# check if the argument types are correct
	for current_arg, current_arg_type in annotations.items():
		if current_arg not in prepared_args:
			continue

		current_arg_value = prepared_args[current_arg]

		# if the type is a ForwardRef or str, ignore it
		if isinstance(current_arg_type, ForwardRefOrStr):
			continue
		elif any(isinstance(x, ForwardRefOrStr) for x in getattr(current_arg_type, "__args__", [])):
			continue
		# ignore unittest.mock objects
		elif isinstance(current_arg_value, mock.Mock):
			continue

		# allow slack for Frappe types
		if current_arg_type in SLACK_DICT:
			current_arg_type = SLACK_DICT[current_arg_type]

		param_def = func_params.get(current_arg)

		# add default value's type in acceptable types
		if param_def.default is not _empty:
			if isinstance(current_arg_type, tuple):
				if type(param_def.default) not in current_arg_type:
					current_arg_type += (type(param_def.default),)
				current_arg_type = Union[current_arg_type]  # noqa: UP007

			elif param_def.default != current_arg_type:
				current_arg_type = Union[current_arg_type, type(param_def.default)]  # noqa: UP007
		elif isinstance(current_arg_type, tuple):
			current_arg_type = Union[current_arg_type]  # noqa: UP007

		# validate the type set using pydantic - raise a TypeError if Validation is raised or Ellipsis is returned
		try:
			current_arg_value_after = TypeAdapter(current_arg_type).validate_python(current_arg_value)
		except (TypeError, PydanticValidationError) as e:
			raise_type_error(func, current_arg, current_arg_type, current_arg_value, current_exception=e)

		if isinstance(current_arg_value_after, EllipsisType):
			raise_type_error(func, current_arg, current_arg_type, current_arg_value)

		# update the args and kwargs with possibly casted value
		if current_arg in kwargs:
			new_kwargs[current_arg] = current_arg_value_after
		else:
			new_args[arg_names.index(current_arg)] = current_arg_value_after

	return new_args, new_kwargs
