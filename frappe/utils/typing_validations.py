from inspect import _empty, signature
from typing import Callable, ForwardRef, Union

from typeguard import check_type

SLACK_DICT = {
	bool: (int, bool, float),
}


def validate_argument_types(func: Callable, args: tuple, kwargs: dict):
	"""
	Validate the types of the arguments passed to a function with the type annotations
	defined on the function.

	"""
	if annotations := func.__annotations__:
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

			check_type(current_arg, current_arg_value, current_arg_type)
