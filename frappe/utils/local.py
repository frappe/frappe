from contextvars import ContextVar
from typing import Any, Generic, TypeVar

from werkzeug.local import LocalProxy as _LocalProxy
from werkzeug.local import _ProxyLookup
from werkzeug.local import release_local as _release_local

_contextvar = ContextVar("frappe_local")

T = TypeVar("T")


class Local:
	"""
	For internal use only. Do not use this class directly.
	"""

	__slots__ = ()

	def __getattribute__(self, name: str) -> Any:
		# this is not needed as long as we have no other attributes than special methods
		# if name in _local_attributes:
		# 	return object.__getattribute__(self, name)

		obj = _contextvar.get(None)
		if obj is not None and name in obj:
			return obj[name]

		raise AttributeError(name)

	def __iter__(self):
		return iter((_contextvar.get({})).items())

	def __setattr__(self, name: str, value: Any) -> None:
		obj = _contextvar.get(None)
		if obj is None:
			obj = {}
			_contextvar.set(obj)

		obj[name] = value

	def __delattr__(self, name: str) -> None:
		obj = _contextvar.get(None)
		if obj is not None and name in obj:
			del obj[name]
			return

		raise AttributeError(name)

	def __call__(self, name: str) -> "LocalProxy":
		def _get_current_object() -> Any:
			obj = _contextvar.get(None)
			if obj is not None and name in obj:
				return obj[name]

			raise RuntimeError("object is not bound") from None

		lp = LocalProxy(_get_current_object)
		object.__setattr__(lp, "_get_current_object", _get_current_object)
		return lp


class LocalProxy(Generic[T]):
	__slots__ = _LocalProxy.__slots__
	__init__ = _LocalProxy.__init__

	for attr, val in vars(_LocalProxy).items():
		if attr == "__getattr__" or not isinstance(val, _ProxyLookup):
			continue

		locals()[attr] = val

	def __getattribute__(self, name: str) -> Any:
		if name in _local_proxy_attributes:
			return object.__getattribute__(self, name)

		return getattr(get_obj(self), name)

	def __setattr__(self, name: str, value: str) -> None:
		setattr(get_obj(self), name, value)

	def __delattr__(self, name: str) -> None:
		delattr(get_obj(self), name)

	def __getitem__(self, key: str) -> Any:
		return get_obj(self)[key]

	def __setitem__(self, key: str, value: str) -> None:
		get_obj(self)[key] = value

	def __delitem__(self, key: str) -> None:
		del get_obj(self)[key]

	def __bool__(self) -> bool:
		try:
			return bool(get_obj(self))
		except RuntimeError:
			return False

	def __contains__(self, key: str) -> bool:
		return key in get_obj(self)

	def __str__(self) -> str:
		return str(get_obj(self))


def get_obj(lp: LocalProxy) -> Any:
	return object.__getattribute__(lp, "_get_current_object")()


def release_local(local):
	if isinstance(local, Local):
		_contextvar.set({})
		return

	_release_local(local)


# _local_attributes = frozenset(attr for attr in dir(Local))
_local_proxy_attributes = frozenset(attr for attr in dir(LocalProxy))
