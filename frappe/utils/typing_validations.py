from inspect import _empty, isclass, signature
from types import EllipsisType
from typing import Callable, ForwardRef, Union

from pydantic import parse_obj_as
from pydantic.error_wrappers import ValidationError as PyValidationError

SLACK_DICT = {
	bool: (int, bool, float),
}


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
	arg_name: str, arg_type: type, arg_value: object, current_exception: Exception = None
):
	"""
	Raise a TypeError with a message that includes the name of the argument, the expected type
	and the actual type of the value passed.

	"""
	raise TypeError(
		f"Argument '{arg_name}' should be of type '{qualified_name(arg_type)}' but got "
		f"'{qualified_name(arg_value)}' instead."
	) from current_exception


def transform_parameter_types(func: Callable, args: tuple, kwargs: dict):
	"""
	Validate the types of the arguments passed to a function with the type annotations
	defined on the function.

	"""
	if annotations := func.__annotations__:
		new_args, new_kwargs = list(args), kwargs

		# generate kwargs dict from args
		arg_names = func.__code__.co_varnames[: func.__code__.co_argcount]

		if not args:
			prepared_args = kwargs

		elif kwargs:
			arg_values = args or func.__defaults__ or []
			prepared_args = dict(zip(arg_names, arg_values))
			prepared_args.update(kwargs)

		else:
			prepared_args = dict(zip(arg_names, args))

		# check if type hints dont match the default values
		func_signature = signature(func)
		func_params = dict(func_signature.parameters)

		# check if the argument types are correct
		for current_arg, current_arg_type in annotations.items():
			if current_arg not in prepared_args:
				continue

			current_arg_value = prepared_args[current_arg]

			# if the type is a ForwardRef or str, ignore it
			if isinstance(current_arg_type, (ForwardRef, str)):
				continue
			elif any(isinstance(x, (ForwardRef, str)) for x in getattr(current_arg_type, "__args__", [])):
				continue

			# allow slack for Frappe types
			if current_arg_type in SLACK_DICT:
				current_arg_type = SLACK_DICT[current_arg_type]

			param_def = func_params.get(current_arg)

			# add default value's type in acceptable types
			if param_def.default is not _empty:
				if isinstance(current_arg_type, tuple):
					if param_def.default not in current_arg_type:
						current_arg_type += (type(param_def.default),)
				elif param_def.default != current_arg_type:
					current_arg_type = Union[current_arg_type, type(param_def.default)]

			try:
				current_arg_value_after = parse_obj_as(
					current_arg_type, current_arg_value, type_name=current_arg
				)
			except PyValidationError as e:
				raise_type_error(current_arg, current_arg_type, current_arg_value, current_exception=e)

			if isinstance(current_arg_value_after, EllipsisType):
				raise_type_error(current_arg, current_arg_type, current_arg_value)

			else:
				if current_arg in kwargs:
					new_kwargs[current_arg] = current_arg_value_after
				else:
					new_args[arg_names.index(current_arg)] = current_arg_value_after

		return new_args, new_kwargs

	return args, kwargs
