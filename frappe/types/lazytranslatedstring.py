import functools

from frappe import _


@functools.total_ordering
class _LazyTranslate:
	__slots__ = ("context", "lang", "msg")

	def __init__(self, msg: str, lang: str | None = None, context: str | None = None) -> None:
		self.msg = msg
		self.lang = lang
		self.context = context

	@property
	def value(self) -> str:
		return _(str(self.msg), self.lang, self.context)

	def __str__(self):
		return self.value

	def __add__(self, other):
		if isinstance(other, str | _LazyTranslate):
			return self.value + str(other)
		raise NotImplementedError

	def __radd__(self, other):
		if isinstance(other, str | _LazyTranslate):
			return str(other) + self.value
		return NotImplementedError

	def __repr__(self) -> str:
		return f"'{self.value}'"

	# NOTE: it's required to override these methods and raise error as default behaviour will
	# return `False` in all cases.
	def __eq__(self, other):
		raise NotImplementedError

	def __lt__(self, other):
		raise NotImplementedError
