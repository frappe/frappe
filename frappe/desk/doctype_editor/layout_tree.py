# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""One layout's tree of tabs, sections and columns, edited by the canvas acts."""

from frappe import _
from frappe.desk.doctype.form_layout.form_layout import assign_names
from frappe.desk.doctype_editor.errors import EditError

CONTAINER_PROPERTIES = frozenset(
	(
		"label",
		"hideLabel",
		"description",
		"hideBorder",
		"collapsible",
		"opened",
		"dependsOn",
		"collapsibleDependsOn",
	)
)


class LayoutTree:
	def __init__(self, tabs: list, layout_id: str):
		self.tabs = tabs
		self.layout_id = layout_id

	def fieldnames(self) -> list[str]:
		return [entry for column in self.columns() for entry in column["fields"] if isinstance(entry, str)]

	def sections(self) -> list[dict]:
		return [section for tab in self.tabs for section in tab["sections"]]

	def columns(self) -> list[dict]:
		return [column for section in self.sections() for column in section["columns"]]

	def add_tab(self, name: str | None = None, label: str | None = None, index: int | None = None):
		tab = self.new_node(name, label, "sections")
		self.insert(self.tabs, tab, index)
		assign_names(self.tabs, "tab")

	def add_section(self, tab: str, name=None, label=None, index=None):
		section = self.new_node(name, label, "columns")
		section["columns"].append({"name": "column_1", "fields": []})
		self.insert(self.tab(tab)["sections"], section, index)
		assign_names(self.sections(), "section")

	def add_column(self, section: str, name=None, index=None):
		column = self.new_node(name, None, "fields")
		columns = self.section(section)["columns"]
		self.insert(columns, column, index)
		assign_names(columns, "column")

	def remove_tab(self, tab: str):
		node = self.tab(tab)
		siblings = self.tabs
		if len(siblings) == 1:
			raise self.container_error(_("A layout keeps at least one tab."), tab)
		at = siblings.index(node)
		receiver = siblings[at - 1] if at else siblings[1]
		receiver["sections"].extend(node["sections"])
		siblings.remove(node)

	def remove_section(self, section: str):
		tab, node = self.parent_of_section(section)
		at = tab["sections"].index(node)
		tab["sections"].remove(node)
		receiver = tab["sections"][max(at - 1, 0)] if tab["sections"] else None
		fields = [entry for column in node["columns"] for entry in column["fields"]]
		if fields and receiver and receiver["columns"]:
			receiver["columns"][-1]["fields"].extend(fields)

	def remove_column(self, column: str, section: str | None = None):
		section, node = self.parent_of_column(column, section)
		at = section["columns"].index(node)
		section["columns"].remove(node)
		receiver = section["columns"][max(at - 1, 0)] if section["columns"] else None
		if receiver:
			receiver["fields"].extend(node["fields"])

	def move_tab(self, tab: str, index: int):
		node = self.tab(tab)
		self.tabs.remove(node)
		self.tabs.insert(index, node)

	def move_section(self, section: str, tab: str, index: int):
		old_tab, node = self.parent_of_section(section)
		old_tab["sections"].remove(node)
		self.tab(tab)["sections"].insert(index, node)

	def move_column(self, column: str, to_section: str, index: int, section: str | None = None):
		old_section, node = self.parent_of_column(column, section)
		old_section["columns"].remove(node)
		self.insert(self.section(to_section)["columns"], node, index)
		assign_names(self.section(to_section)["columns"], "column")

	def set_container_property(self, container: str, property: str, value, section: str | None = None):
		if property not in CONTAINER_PROPERTIES:
			raise self.container_error(_("{0} is not a container property.").format(property), container)
		node = self.column(container, section) if section else self.container(container)
		if value in (None, "", False, 0):
			node.pop(property, None)
		else:
			node[property] = value

	def place_field(self, fieldname: str, column=None, index: int | None = None, tab=None, section=None):
		self.unplace_field(fieldname)
		if tab:
			target = self.tab(tab)
			if not target["sections"]:
				self.add_section(tab)
			fields = target["sections"][0]["columns"][-1]["fields"]
		else:
			fields = self.column(column, section)["fields"]
		fields.insert(len(fields) if index is None else index, fieldname)

	def unplace_field(self, fieldname: str):
		for column in self.columns():
			column["fields"] = [entry for entry in column["fields"] if entry != fieldname]

	def rename_field(self, old: str, new: str):
		for column in self.columns():
			column["fields"] = [new if entry == old else entry for entry in column["fields"]]

	def tab(self, name: str) -> dict:
		return self.find(self.tabs, name)

	def section(self, name: str) -> dict:
		return self.find(self.sections(), name)

	def column(self, name: str, section: str | None = None) -> dict:
		"""Column names repeat across sections, so an unscoped name must be unique in the layout."""
		if section:
			return self.find(self.section(section)["columns"], name)
		matches = [column for column in self.columns() if column["name"] == name]
		if len(matches) > 1:
			raise self.container_error(_("Name the section of column {0}.").format(name), name)
		return self.find(matches, name)

	def container(self, name: str) -> dict:
		return self.find([*self.tabs, *self.sections()], name)

	def parent_of_section(self, name: str) -> tuple[dict, dict]:
		node = self.section(name)
		return next(tab for tab in self.tabs if node in tab["sections"]), node

	def parent_of_column(self, name: str, section: str | None = None) -> tuple[dict, dict]:
		node = self.column(name, section)
		return next(section for section in self.sections() if node in section["columns"]), node

	def find(self, nodes: list[dict], name: str) -> dict:
		for node in nodes:
			if node["name"] == name:
				return node
		raise self.container_error(_("This layout has no {0}.").format(name), name)

	@staticmethod
	def new_node(name: str | None, label: str | None, children_key: str) -> dict:
		node = {children_key: []}
		if name:
			node["name"] = name
		if label:
			node["label"] = label
		return node

	@staticmethod
	def insert(siblings: list, node: dict, index: int | None):
		siblings.insert(len(siblings) if index is None else index, node)

	def container_error(self, message: str, container: str) -> EditError:
		return EditError(message, kind="container", layout=self.layout_id, container=container)
