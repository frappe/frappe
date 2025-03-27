from collections.abc import Iterable, Mapping
from typing import (
	TYPE_CHECKING,
	TypeVar,
	overload,
)

from typing_extensions import Self, override

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class _dict(dict[_KT, _VT]):
	"""dict like object that exposes keys as attributes"""

	__slots__ = ()

	# NOTE(perf): Do NOT use super() here, it's an unnecessary function call!
	# Refer: https://github.com/frappe/frappe/pull/16449

	__getattr__ = dict.get
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__
	__setstate__ = dict.update

	@override
	def __getstate__(self) -> Self:
		return self

	@overload  # type: ignore[override]
	def update(self, m: Mapping[_KT, _VT], /, **kwargs: _VT) -> Self: ...

	@overload
	def update(self, m: Iterable[tuple[_KT, _VT]], /, **kwargs: _VT) -> Self: ...

	@overload
	def update(self, /, **kwargs: _VT) -> Self: ...

	@override
	def update(
		self, m: Mapping[_KT, _VT] | Iterable[tuple[_KT, _VT]] | None = None, /, **kwargs: _VT
	) -> Self:
		"""update and return self -- the missing dict feature in python"""
		if m:
			super().update(m, **kwargs)
		else:
			super().update(**kwargs)
		return self

	@override
	def copy(self) -> "_dict[_KT, _VT]":
		return _dict(self)
