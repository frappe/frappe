"""Write the input rows of a site's own components as props in the component's script.

A standard component is skipped: its JSON file is its source, so the app's repository must change.
"""

import json
import re

import click

import frappe

PROP_TYPES = {
	"text": "String",
	"textarea": "String",
	"select": "String",
	"color": "String",
	"number": "Number",
	"checkbox": "Boolean",
}
IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")
INPUT_FIELDS = ["input_name", "type", "description", "options", "required", "default"]


def execute():
	skipped = []
	components = frappe.get_all("Studio Component", filters={"is_standard": 0}, fields=["name", "script"])
	for component in components:
		rows = {"parent": component.name, "parenttype": "Studio Component"}
		inputs = frappe.get_all(
			"Studio Component Input", filters=rows, fields=INPUT_FIELDS, order_by="idx asc"
		)
		if not inputs or (component.script or "").strip():
			continue
		if not all(can_be_prop_default(input) for input in inputs):
			skipped.append(component.name)
			continue
		frappe.db.set_value(
			"Studio Component", component.name, "script", get_script(inputs), update_modified=False
		)
		frappe.db.delete("Studio Component Input", rows)

	if skipped:
		click.echo(
			"These Studio components keep their input rows, because a default value has no equal as a "
			"prop default. Declare their props in a script:\n" + "\n".join(f"  {name}" for name in skipped)
		)


def can_be_prop_default(input) -> bool:
	"""A row's default is text that reaches the component as a string, after its `{{ }}` bindings
	are evaluated. A prop default is a fixed value of the prop's type."""
	default = input.default or ""
	return not default or ("{{" not in default and input.type not in ("number", "checkbox"))


def get_script(inputs) -> str:
	props = "".join(f"\t\t{get_prop(input)},\n" for input in inputs)
	return f"export default {{\n\tprops: {{\n{props}\t}},\n}}\n"


def get_prop(input) -> str:
	"""One entry of the `props` object, as the editor's form writes it."""
	prop_type = PROP_TYPES.get(input.type)
	parts = [f"type: {prop_type}"] if prop_type else []
	if input.required:
		parts.append("required: true")
	if input.default:
		parts.append(f"default: {json.dumps(input.default)}")

	meta = []
	if input.type in ("textarea", "select", "color"):
		meta.append(f'control: "{input.type}"')
	if input.type == "select":
		options = [option for option in (input.options or "").split("\n") if option.strip()]
		meta.append(f"options: {json.dumps(options, separators=(',', ':'))}")
	if input.description:
		meta.append(f"description: {json.dumps(input.description)}")
	if meta:
		parts.append(f"meta: {{ {', '.join(meta)} }}")

	name = input.input_name if IDENTIFIER.fullmatch(input.input_name) else json.dumps(input.input_name)
	if parts == [f"type: {prop_type}"]:
		return f"{name}: {prop_type}"
	return f"{name}: {{ {', '.join(parts)} }}" if parts else f"{name}: null"
