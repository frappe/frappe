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
	def __hash__(self) -> int:
		if self.name:
			return hash(self.doctype + self.name)
		else:
			raise ValueError("Only named documents can be hashed; maybe the document is unsaved.")

	@override
	def __str__(self) -> str:
		return f"{self.doctype} ({self.name or 'n/a'})"

	@override
	def __repr__(self) -> str:
		return f"<{self.__class__.__name__}: doctype={self.doctype} name={self.name or 'n/a'}>"
