class _dict(dict):
	"""dict like object that exposes keys as attributes"""

	__slots__ = ()
	__getattr__ = dict.get
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__
	__setstate__ = dict.update

	def __getstate__(self):
		return self

<<<<<<< HEAD
	def update(self, *args, **kwargs):
=======
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
>>>>>>> 84ef6ec677 (refactor: fixup with ruff 0.8.1)
		"""update and return self -- the missing dict feature in python"""

		super().update(*args, **kwargs)
		return self

	def copy(self):
		return _dict(self)
