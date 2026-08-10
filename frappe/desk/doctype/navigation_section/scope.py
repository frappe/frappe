# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Where a Navigation Section lives: an app, and inside it a doctype's sidebar or the app itself."""

from dataclasses import dataclass

DEFAULT_APP = "frappe"

UNSET = ("in", ("", None))


@dataclass(frozen=True)
class Scope:
	app: str = DEFAULT_APP
	reference_doctype: str = ""

	@property
	def is_app_level(self) -> bool:
		return not self.reference_doctype

	def filters(self) -> dict:
		"""Filters selecting this scope's sections and nothing else."""
		return {
			"app": self.app,
			"reference_doctype": UNSET if self.is_app_level else self.reference_doctype,
		}

	def as_fields(self) -> dict:
		"""The scope keys a new section is created with."""
		return {"app": self.app, "reference_doctype": self.reference_doctype}


def scope_of(section) -> Scope:
	"""The scope a stored section belongs to. Takes a dict or a Document."""
	return Scope(section.get("app") or "", section.get("reference_doctype") or "")
