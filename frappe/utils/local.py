from contextvars import ContextVar
from typing import Any, Generic, TypeVar

from werkzeug.local import LocalProxy as WerkzeugLocalProxy
from werkzeug.local import release_local as release_werkzeug_local

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


class LocalProxy(WerkzeugLocalProxy, Generic[T]):
	__slots__ = ()

	def __getattr__(self, name: str) -> Any:
		return getattr(self._get_current_object(), name)

	def __setattr__(self, name: str, value: str) -> None:
		setattr(self._get_current_object(), name, value)

	def __delattr__(self, name: str) -> None:
		delattr(self._get_current_object(), name)

	def __getitem__(self, key: str) -> Any:
		return self._get_current_object()[key]

	def __setitem__(self, key: str, value: str) -> None:
		self._get_current_object()[key] = value

	def __delitem__(self, key: str) -> None:
		del self._get_current_object()[key]

	def __bool__(self) -> bool:
		try:
			return bool(self._get_current_object())
		except RuntimeError:
			return False

	def __contains__(self, key: str) -> bool:
		return key in self._get_current_object()

	def __str__(self) -> str:
		return str(self._get_current_object())


def release_local(local):
	if isinstance(local, Local):
		_contextvar.set({})
		return

	release_werkzeug_local(local)


# _local_attributes = frozenset(attr for attr in dir(Local))
