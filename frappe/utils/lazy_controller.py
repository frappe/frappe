"""Lazy controller proxy.

`make_lazy_controller(name, module_path, attr)` returns a class-like object that
defers importing `module_path` until the class is actually USED — instantiated,
checked with isinstance/issubclass, subclassed, or has an attribute looked up.

Bare imports like `from frappe.desk.doctype import ToDo` do not trigger loading.
"""

from importlib import import_module


class _LazyControllerMeta(type):
	def _resolve(cls):
		resolved = cls.__dict__.get("_resolved")
		if resolved is None:
			module_path, attr = cls.__dict__["_target"]
			resolved = getattr(import_module(module_path), attr)
			type.__setattr__(cls, "_resolved", resolved)
		return resolved

	def __call__(cls, *args, **kwargs):
		return cls._resolve()(*args, **kwargs)

	def __instancecheck__(cls, instance):
		return isinstance(instance, cls._resolve())

	def __subclasscheck__(cls, sub):
		return issubclass(sub, cls._resolve())

	def __mro_entries__(cls, bases):
		# Subclassing: `class Sub(LazyToDo): ...` — substitute the real class.
		return (cls._resolve(),)

	def __getattr__(cls, name):
		# Triggered only when normal MRO lookup fails. Dunder access on the
		# class itself (e.g. __name__, __module__) is satisfied by the proxy's
		# own dict and never reaches here, so dunder loops are avoided.
		if name.startswith("__") and name.endswith("__"):
			raise AttributeError(name)
		return getattr(cls._resolve(), name)

	def __repr__(cls):
		resolved = cls.__dict__.get("_resolved")
		if resolved is not None:
			return repr(resolved)
		module_path, attr = cls.__dict__["_target"]
		return f"<lazy class {module_path}.{attr}>"


def make_lazy_controller(name: str, module_path: str, attr: str, *, defined_in: str):
	return _LazyControllerMeta(
		name,
		(),
		{
			"_target": (module_path, attr),
			"_resolved": None,
			"__module__": defined_in,
			"__qualname__": name,
		},
	)
