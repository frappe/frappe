# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.studio.export import (
	SYNC_FLAGS,
	can_export,
	delete_file,
	parse_json,
	remove_empty_values,
	validate_frappe_app,
	validate_standard_app_change,
	write_code_file,
	write_document_file,
)
from frappe.studio.realtime import publish_doc_change
from frappe.studio.sync_json import COMPONENT_FOLDER, get_studio_folders
from frappe.studio.utils import (
	IMPORT_RE,
	find_script_file,
	get_export_folder,
	get_exported_app_folders,
	get_exported_app_name,
	get_studio_folder,
	script_extension,
	validate_file_name,
	walk_blocks,
)


class StudioComponent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.studio.doctype.studio_component_input.studio_component_input import StudioComponentInput
		from frappe.types import DF

		block: DF.LongText | None
		component_id: DF.Data | None
		component_name: DF.Data | None
		frappe_app: DF.Data | None
		inputs: DF.Table[StudioComponentInput]
		is_disabled: DF.Check
		is_standard: DF.Check
		script: DF.Code | None
		studio_app: DF.Link | None
	# end: auto-generated types

	def autoname(self):
		if not self.component_id:
			self.component_id = append_number_if_name_exists(
				"Studio Component",
				frappe.scrub(self.component_name),
				fieldname="component_id",
				separator="_",
				filters={"studio_app": self.studio_app or ("is", "not set")},
			)
		validate_component_id(self.component_id)
		self.name = get_component_name(self.component_id, self.studio_app)

	def before_export(self, doc):
		doc.block = parse_json(doc.block)
		if doc.block:
			remove_empty_values(doc.block)

	def before_validate(self):
		if isinstance(self.block, dict):
			self.block = frappe.as_json(self.block, indent=None)

	def validate(self):
		self.validate_frappe_app()
		validate_standard_app_change(self)
		# the docname holds the id, so the two cannot disagree
		self.component_id = get_component_id(self.name)
		if not self.studio_app:
			self.validate_no_app_dependencies()
		self.validate_legacy_inputs()

	def validate_frappe_app(self):
		"""A Frappe app can hold a global component in its files. An app's component is in the
		files of its Studio App."""
		if not self.frappe_app:
			return
		if self.studio_app:
			frappe.throw(_("Only a global component can belong to a Frappe app."))
		validate_frappe_app(self)
		self.is_standard = 1

	def validate_legacy_inputs(self):
		"""The props of a component are in its script. The input rows of an older component can
		stay or go, and the files of an app can still bring them."""
		if self.flags.is_moved or any(frappe.flags.get(flag) for flag in SYNC_FLAGS):
			return
		before = self.get_doc_before_save()
		saved_rows = [get_input_values(row) for row in before.inputs] if before else []
		if any(get_input_values(row) not in saved_rows for row in self.inputs):
			frappe.throw(
				_("You cannot add or edit input rows. Define props in the component's script instead."),
				title=_("Input rows are deprecated"),
			)

	def validate_no_app_dependencies(self):
		"""A global component renders in every app, and outside an app. So it cannot use the
		files of one app."""
		if imports := IMPORT_RE.findall(self.script or ""):
			frappe.throw(
				_(
					'A global component cannot import a file of one app: {0}. Import only libraries such as "vue", or edit the component and uncheck "Global Component".'
				).format(", ".join(imports)),
				title=_("Script not saved"),
			)
		is_edit = self.has_value_changed("block") and not any(frappe.flags.get(flag) for flag in SYNC_FLAGS)
		if is_edit and (app_components := get_app_vue_components(self.block)):
			frappe.msgprint(
				_(
					'This global component will not work in other apps. It uses {0} from this app. To keep it local to this app, edit the component and uncheck "Global Component".'
				).format(", ".join(app_components)),
				title=_("Global component uses an app's Vue component"),
				indicator="orange",
			)

	@frappe.whitelist()
	def set_app(self, studio_app: str | None = None) -> dict:
		"""Move a global component to `studio_app`, or make an app's component global when no app
		is given. The id stays, so the docname changes and the blocks that use it do not.

		A global component stays, beside the app's new one, when another app uses it."""
		self.check_permission("write")
		studio_app = studio_app or None
		if studio_app == (self.studio_app or None):
			return {"name": self.name, "is_global_kept": False}
		if studio_app:
			frappe.has_permission("Studio App", ptype="write", doc=studio_app, throw=True)
		elif frappe.db.exists("Studio Component", self.component_id):
			frappe.throw(_("A global component with the ID {0} already exists.").format(self.component_id))

		folders = self.get_export_folders()
		moved = frappe.copy_doc(self)
		moved.studio_app = studio_app
		moved.flags.is_moved = True
		moved.insert()
		is_global_kept = bool(studio_app) and bool(self.get_usages())
		if not is_global_kept:
			# the moved component takes over the files and the blocks that use the id
			self.flags.is_moved = True
			self.delete()
		for folder in folders if not studio_app else moved.get_export_folders():
			moved.export_to_folder(folder)
		return {"name": moved.name, "is_global_kept": is_global_kept}

	@frappe.whitelist()
	def get_usages(self) -> list[str | None]:
		"""Titles of the pages and components that have a block which still means this component.
		The title is None for one that the user cannot read."""
		self.check_permission("read")
		usages = []
		for doctype, title_field, tree_fields, label in (
			("Studio Component", "component_name", ["block"], _("{0} (component)")),
			("Studio Page", "page_title", ["blocks", "draft_blocks"], _("{0} (page)")),
		):
			for doc in self.get_referencing_docs(doctype, self.component_id, [title_field, *tree_fields]):
				if any(self.is_in_blocks(doc[field]) for field in tree_fields):
					can_read = frappe.has_permission(doctype, "read", doc=doc.name)
					usages.append(label.format(doc[title_field]) if can_read else None)
		return usages

	def is_in_blocks(self, tree: str | None) -> bool:
		return bool(tree) and self.component_id in extract_component_names(tree)

	def validate_not_used(self):
		usages = self.get_usages()
		titles = [title for title in usages if title]
		if hidden := len(usages) - len(titles):
			if titles:
				text = _("and {0} more that you cannot access")
			elif hidden == 1:
				text = _("{0} place that you cannot access")
			else:
				text = _("{0} places that you cannot access")
			titles.append(text.format(hidden))
		if usages:
			frappe.throw(
				_("{0} is used in: {1}. Remove it from there first.").format(
					self.component_name, ", ".join(titles)
				),
				title=_("Component not deleted"),
				exc=frappe.LinkExistsError,
			)

	def before_rename(self, old, new, merge=False):
		"""Renaming the document changes the component's id. The new name can be the id alone."""
		if merge:
			frappe.throw(_("Components cannot be merged."))
		validate_standard_app_change(self)
		owner, _separator, component_id = new.rpartition("/")
		if owner and owner != self.studio_app:
			frappe.throw(_("A component cannot move to another app."))
		validate_component_id(component_id)
		return {"new": get_component_name(component_id, self.studio_app)}

	def after_rename(self, old, new, merge=False):
		old_id, new_id = get_component_id(old), get_component_id(new)
		if old_id == new_id:
			# its app was renamed, which moves the files and keeps the id
			return
		self.component_id = old_id
		folders = self.get_export_folders()
		for folder in folders:
			rename_component_files(folder, frappe.scrub(old_id), frappe.scrub(new_id))
		self.db_set("component_id", new_id, update_modified=False)
		for folder in folders:
			self.export_to_folder(folder)
		self.rename_references(old_id, new_id)

	def rename_references(self, old_id: str, new_id: str):
		"""Point every block that meant this component at its new id."""
		for component in self.get_referencing_docs("Studio Component", old_id):
			doc = frappe.get_doc("Studio Component", component.name)
			block = parse_json(doc.block)
			if not rename_component_in_blocks(block, old_id, new_id):
				continue
			doc.block = block
			doc.save()
			for folder in doc.get_export_folders():
				doc.export_to_folder(folder)

		for page in self.get_referencing_docs("Studio Page", old_id):
			doc = frappe.get_doc("Studio Page", page.name)
			trees = {field: parse_json(doc.get(field)) for field in ("blocks", "draft_blocks")}
			if not any([rename_component_in_blocks(tree, old_id, new_id) for tree in trees.values()]):
				continue
			for field, tree in trees.items():
				if tree:
					doc.set(field, frappe.as_json(tree, indent=None))
			doc._skip_validate = True  # blocks only change
			doc.save()

	def get_referencing_docs(self, doctype: str, old_id: str, fields: list[str] | None = None) -> list[dict]:
		"""Pages or components whose blocks can mean this component by `old_id`: those of its app,
		or for a global component, those of every app that has no component of its own with that id."""
		fields = ["name", "studio_app", *(fields or [])]
		if self.studio_app:
			return frappe.get_all(doctype, filters={"studio_app": self.studio_app}, fields=fields)
		apps_with_their_own = frappe.get_all(
			"Studio Component",
			filters={"component_id": old_id, "studio_app": ("is", "set")},
			pluck="studio_app",
		)
		docs = frappe.get_all(doctype, fields=fields)
		return [doc for doc in docs if doc.studio_app not in apps_with_their_own]

	def on_update(self):
		if can_export(self) and self.frappe_app:
			folder = get_frappe_app_component_folder(self.frappe_app)
			os.makedirs(folder, exist_ok=True)
			self.export_to_folder(folder)
		if can_export(self) and self.has_value_changed("script"):
			for folder in self.get_export_folders():
				self.write_script_file(folder)
		publish_doc_change("Studio Component", self.name)

	def on_trash(self):
		validate_standard_app_change(self)
		if self.flags.is_moved:
			return
		if not self.flags.is_app_deleted:
			self.validate_not_used()
		# uninstalling an app from a site leaves the app's files
		if frappe.conf.developer_mode and not frappe.flags.in_uninstall:
			self.delete_files()

	def export_to_folder(self, folder: str):
		"""Write the component's JSON, and its script when the folder has none.

		The script file is the copy a developer edits, so only a changed `script` field replaces it."""
		write_document_file(self, folder=folder, exclude_fields=["script"], filename=self.get_file_stem())
		if self.script and not os.path.exists(self.get_script_file_path(folder)):
			self.write_script_file(folder)

	def write_script_file(self, folder: str):
		"""An existing file keeps its language. A new one is JavaScript, the language of the `script` field."""
		stem = self.get_file_stem()
		if self.script:
			extension = script_extension(folder, stem, default="js")
			write_code_file(self, folder, code_field="script", extension=extension, filename=stem)
		else:
			delete_file(self.get_script_file_path(folder))

	def get_script_file_path(self, folder: str) -> str:
		return find_script_file(folder, self.get_file_stem())

	def get_file_stem(self) -> str:
		return frappe.scrub(self.component_id)

	def get_export_folders(self) -> list[str]:
		"""The folders that hold this component's files. An app's component is in the app's folder.
		Every standard page using a global component exports it, so its files can be in several apps."""
		if self.studio_app:
			frappe_app = frappe.db.get_value("Studio App", self.studio_app, "frappe_app")
			folders = [get_export_folder(frappe_app, self.studio_app)] if frappe_app else []
		else:
			folders = [
				# the Frappe app that holds it, then each Studio App that exported a copy
				*([get_studio_folder(self.frappe_app)] if self.frappe_app else []),
				*self.get_exporting_app_folders(),
			]
		return [
			folder
			for folder in (os.path.join(app_folder, COMPONENT_FOLDER) for app_folder in folders)
			if os.path.exists(os.path.join(folder, f"{self.get_file_stem()}.json"))
		]

	def get_exporting_app_folders(self) -> list[str]:
		return [
			app_folder
			for studio_folder in get_studio_folders()
			for app_folder in get_exported_app_folders(studio_folder)
			# an app's own component with this id uses the same file name
			if not frappe.db.exists(
				"Studio Component",
				get_component_name(self.component_id, get_exported_app_name(app_folder)),
			)
		]

	def delete_files(self):
		for folder in self.get_export_folders():
			delete_component_files(folder, self.get_file_stem())


def get_frappe_app_component_folder(frappe_app: str) -> str:
	"""The folder for the global components that a Frappe app holds, which need no Studio App."""
	return os.path.join(get_studio_folder(frappe_app), COMPONENT_FOLDER)


def rename_component_files(folder: str, old_stem: str, new_stem: str):
	old_script = find_script_file(folder, old_stem)
	if os.path.exists(old_script):
		os.replace(old_script, os.path.join(folder, new_stem + os.path.splitext(old_script)[1]))
	os.replace(os.path.join(folder, f"{old_stem}.json"), os.path.join(folder, f"{new_stem}.json"))


def rename_component_in_blocks(blocks, old_id: str, new_id: str) -> bool:
	"""Rename the component in a parsed block tree. Return whether a block changed."""
	renamed = False
	for block in walk_blocks(blocks):
		if block.get("isStudioComponent") and block.get("componentName") == old_id:
			block["componentName"] = new_id
			renamed = True
	return renamed


def get_app_vue_components(blocks) -> list[str]:
	"""Names of the app `.vue` components that a block tree uses."""
	names = {block.get("componentName") for block in walk_blocks(blocks) if block.get("isCustomVueComponent")}
	return sorted(name for name in names if name)


def validate_component_id(component_id: str | None):
	# the scrubbed id names the component's exported file, so it must stay a single path segment
	validate_file_name(
		component_id,
		_("Component ID cannot be empty or contain slashes."),
		title=_("Invalid Component ID"),
	)


def delete_component_files(folder: str, stem: str):
	delete_file(find_script_file(folder, stem))
	delete_file(folder, f"{stem}.json")


def mark_components_standard(names: list[str]):
	"""A component with a file in an app is standard, whether or not the file says so"""
	frappe.db.set_value(
		"Studio Component", {"name": ["in", names], "is_standard": 0}, "is_standard", 1, update_modified=False
	)


def get_input_values(row) -> list[str]:
	fields = ("input_name", "type", "description", "options", "required", "default")
	return [frappe.utils.cstr(row.get(field) or "") for field in fields]


def get_component_name(component_id: str, studio_app: str | None = None) -> str:
	"""The docname. An id is unique only inside its app, so an app's component carries the app's name."""
	return f"{studio_app}/{component_id}" if studio_app else component_id


def get_component_id(name: str) -> str:
	return name.rpartition("/")[2]


def find_component(component_id: str, studio_app: str | None = None) -> str | None:
	"""The docname of the component that `component_id` means in `studio_app`: the app's own
	component, or else the global one."""
	names = [get_component_name(component_id, studio_app), component_id]
	return next((name for name in names if frappe.db.exists("Studio Component", name)), None)


def get_components_for_blocks(blocks, studio_app: str | None = None) -> list[dict]:
	"""Fetch component definitions referenced by a block tree, one depth at a time.
	The trees reference a component by its id, which `studio_app` resolves."""
	components = []
	requested_components = set()
	to_fetch = extract_component_names(blocks)
	while to_fetch:
		requested_components.update(to_fetch)
		batch = fetch_component_batch(to_fetch, studio_app)
		components.extend(batch)
		to_fetch = get_nested_component_names(batch) - requested_components
	return components


def extract_component_names(blocks) -> set[str]:
	return {
		block["componentName"]
		for block in walk_blocks(blocks)
		if block.get("isStudioComponent") and block.get("componentName")
	}


def get_nested_component_names(components) -> set[str]:
	names = set()
	for component in components:
		names.update(extract_component_names(component["block"]))
	return names


def fetch_component_batch(component_ids: set[str], studio_app: str | None = None) -> list[dict]:
	"""The components that these ids mean in `studio_app`. The app's own component hides a global
	one with the same id."""
	names = [get_component_name(component_id, studio_app) for component_id in component_ids]
	found = frappe.get_all(
		"Studio Component",
		filters={"name": ["in", [*names, *component_ids]]},
		fields=["name", "component_name", "component_id", "studio_app", "block", "script", "is_disabled"],
		order_by="studio_app desc",
	)
	components = list({component.component_id: component for component in reversed(found)}.values())
	if not components:
		return []

	inputs_by_component = {}
	input_rows = frappe.get_all(
		"Studio Component Input",
		filters={"parenttype": "Studio Component", "parent": ["in", [c.name for c in components]]},
		fields=["name", "parent", "input_name", "type", "description", "options", "required", "default"],
		order_by="idx asc",
	)
	for row in input_rows:
		inputs_by_component.setdefault(row.pop("parent"), []).append(row)

	for component in components:
		component["inputs"] = inputs_by_component.get(component.name, [])
	return components
