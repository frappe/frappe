from typing import Union

from typing_extensions import override


class DocRef:
	"""A lightweight reference to a document, containing just the doctype and name."""

	def __init__(self, doctype: str, name: str):
		self.doctype = doctype
		self.name = name

	def __value__(self) -> str:
		# Used when requiring its value representation for db interactions, serializations, etc
		return self.name

	@override
	def __hash__(self: Union[type, "DocRef"]) -> int:
		if isinstance(self, DocRef):
			if self.name:
				return hash(self.doctype + self.name)
			else:
				raise TypeError(
					f"Only named documents can be hashed; maybe the document ({self.doctype}) is unsaved."
				)
		raise TypeError("Only document instances can be hashed.")

	@override
	def __str__(self) -> str:
		return f"{self.doctype} ({self.name or 'n/a'})"

	@override
	def __repr__(self) -> str:
		return f"<{self.__class__.__name__}: doctype={self.doctype} name={self.name or 'n/a'}>"
