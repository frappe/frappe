import inspect
from collections.abc import Callable
from functools import lru_cache, wraps
from inspect import _empty, isclass
from types import EllipsisType
from typing import ForwardRef, TypeVar, Union, get_type_hints
from unittest import mock
from copy import deepcopy

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


def validate_argument_types(
	func: Callable,
	apply_condition: Callable | None = None,
	force_types: bool | None = None,
):
	# NOTE: this is evaluated/called during declaration (@whitelist) (i.e at compile time kind of) so better to do a lot of checking here!
	app = func.__module__.split(".")[0]


	# Evaluate default values for functions parameters. For default values we do 2 things, if only default value with no annotation, we update the `__annotations__` to reflect the type(default), if default and with annotation, we create a UNION.
	# TODO: ideally we should prevent any default values with mismatched type, like if for float type as annotation, no int values, as this would be caught during declaration and force user to provide expected type for default value.
	new_annotations = deepcopy(func.__annotations__)
	func_params = inspect.signature(func).parameters
	for (param_name, parameter) in func_params.items():
		if not(parameter.default == inspect._empty):
			if  param_name in new_annotations:
				# have a default value and an annotation. Union would handle if both types are same! (a set)
				new_annotations[param_name] = Union[new_annotations[param_name], type(parameter.default)]
			else:
				# have a default value but no annotation.
				assert not(param_name in new_annotations)  # sanity check.
				new_annotations[param_name] = type(parameter.default)
	assert len(new_annotations) >= len(func.__annotations__)  # sanity check.
	func.__annotations__ = new_annotations   # overwriting. (This would be reflected in `get_type_hints` as well when we later use that...)
	del new_annotations

	# Checking annotations as soon as can.(during decoration itself).
	# would be part of closure environment. (have to do it as `force_types = any ..` code should only be used after `frappe` proper resolution.. stop making it more dynamic !!!!
	annotations = func.__annotations__
	are_annotations_comprehensive = True
	invalid_param_name = None
	for idx, (param_name, parameter) in enumerate(func_params.items()):
		if idx == 0 and param_name in ("self", "cls"):
			continue
		if parameter.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
			continue
		if not (param_name in annotations):
			are_annotations_comprehensive = False   # stored in closure environment, so much easier to access when wrapper would actually be called!
			invalid_param_name = param_name
			break
	del annotations, func_params

	# Resolving whatever forwardRefs at declaration time!
	are_forwardRef_resolved:bool = False    # private, would be part of closure environment. (trapped)
	try:
		func.__annotations__ = get_type_hints(func)  # it should handle both aka `forwardRef or str` recursively!
		are_forwardRef_resolved = True
	except Exception as e:
		# Should only get an error, when `ForwardRef or str` annotations couldn't be resolved. `get_type_hints` handles a lot of common cases like missing annotations without throwing errors Its ok, we will try again at runtime.
		pass

	@wraps(func)
	def wrapper(*args, **kwargs):
		"""Validate argument types of whitelisted functions.

		:param args: Function arguments.
		:param kwargs: Function keyword arguments."""

		nonlocal force_types, are_forwardRef_resolved

		# Resolve it only once
		if force_types is None:
			force_types = any(frappe.get_hooks("require_type_annotated_api_methods", app_name=app))

		# NOTE: force_types value depends on `frappe` module, which have to be resolved, otherwise we could have raised "not Annotations present" error in the decorator itself during startup!
		if force_types and not (are_annotations_comprehensive):
			# NOTE: are_annotations_comprehensive is evaluated during the `declaration/decoration` (by @whitelist) and then only checked if `force_types` has been set to True. (force_types) comes from this `frappe` module itself, so we have to wait it for fully resolved to get `force_types` correct value :(
			module, qualname = func.__module__, func.__qualname__
			raise FrappeTypeError(
				f"Argument '{invalid_param_name}' in '{module}.{qualname}' is missing type annotation.."
				f"All arguments must have type annotations when type checking is enforced."
			)

		if not are_forwardRef_resolved:
			# Only if error ocurred earlier this branch would be taken/necessary, meaning there are `annotations` and also `forwardRefs` which couldn't be resolved.
			# get_type_hints, handles cases where there are no annotation for a parameter or if `cls` self like parameters, so if error occured, then it should mean `forwardRefs` failed to get resolved!
			try:
				func.__annotations__ = get_type_hints(func) # No need to pass specific `globalns`, Default works expectedly otherwise we will get an error!
				are_forwardRef_resolved = True				# would be reflected for later calls!
			except Exception as e:
				# We put this conditional check instead in exception block.
				if force_types:
					module, qualname = func.__module__, func.__qualname__
					raise FrappeTypeError(
						f"Couldn't resolve all ForwardRefs for function: {module}.{qualname} as {e}'"
						f"At Runtime All ForwardRefs or ClassName (as string) must have had a Corresponding Class Declared with same name!"
					)
				else:
					pass

		if apply_condition is None or apply_condition():
			# setting `force_types` as False, as would have already that code in the previous block!
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

	# check if the argument types are correct
	for current_arg, current_arg_type in annotations.items():
		if current_arg not in prepared_args:
			continue

		current_arg_value = prepared_args[current_arg]

		# ignore unittest.mock objects
		if isinstance(current_arg_value, mock.Mock):
			continue

		# allow slack for Frappe types
		if current_arg_type in SLACK_DICT:
			current_arg_type = SLACK_DICT[current_arg_type]


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
