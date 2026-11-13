# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE


class EditError(Exception):
	"""A refusal keyed to what the editor shows it on: a field, a container, a layout or the banner."""

	def __init__(self, message: str, **target):
		super().__init__(message)
		self.message = message
		self.target = target or {"kind": "banner"}

	def as_dict(self, edit: int | None = None) -> dict:
		error = {"target": self.target, "message": self.message}
		if edit is not None:
			error["edit"] = edit
		return error


def field_error(message: str, fieldname: str, property: str | None = None) -> EditError:
	target = {"kind": "field", "fieldname": fieldname}
	if property:
		target["property"] = property
	return EditError(message, **target)
