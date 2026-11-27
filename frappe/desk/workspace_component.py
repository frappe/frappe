"""A workspace drawn as a Studio component: a root component whose blocks are widget components.

A workspace with a `studio_component` uses that component's blocks. An older workspace has
`content` and widget tables, and `get_legacy_block` converts them each time the page loads.
Both give a tree that is the same for every user. `WidgetResolver` then applies the session
user's permissions to it.
"""

import frappe
from frappe import _
from frappe.desk.desktop import Workspace as WorkspaceView
from frappe.desk.doctype.workspace.workspace import can_edit_workspace, has_permission
from frappe.desk.utils import is_item_allowed
from frappe.studio.doctype.studio_component.studio_component import get_components_for_blocks
from frappe.utils import strip_html

GRID_COLUMNS = 12
# legacy block type -> (widget component, the key of the block's data that holds the row's label)
LEGACY_WIDGETS = {
	"card": ("desk_links", "card_name"),
	"shortcut": ("desk_shortcut", "shortcut_name"),
	"number_card": ("desk_number_card", "number_card_name"),
	"chart": ("desk_chart", "chart_name"),
	"quick_list": ("desk_quick_list", "quick_list_name"),
}
LINK_FIELDS = (
	"label",
	"link_type",
	"link_to",
	"is_query_report",
	"report_ref_doctype",
	"dependencies",
	"onboard",
)
SHORTCUT_FIELDS = (
	"label",
	"type",
	"link_to",
	"url",
	"doc_view",
	"kanban_board",
	"stats_filter",
	"color",
	"format",
	"restrict_to_domain",
	"report_ref_doctype",
)
# the fields of a record that a widget needs to fetch and print its data
NUMBER_CARD_FIELDS = (
	"type",
	"document_type",
	"function",
	"aggregate_function_based_on",
	"filters_json",
	"dynamic_filters_json",
	"report_name",
	"report_field",
	"report_function",
	"method",
	"currency",
	"show_full_number",
	"show_percentage_stats",
	"stats_time_interval",
	"color",
)
CHART_FIELDS = (
	"chart_type",
	"type",
	"timeseries",
	"color",
	"filters_json",
	"dynamic_filters_json",
	"report_name",
	"use_report_chart",
	"x_field",
)


@frappe.whitelist(methods=["GET"])
def get_workspace_component(workspace: str) -> list[dict]:
	"""The root component of a workspace as the session user sees it, and after it the
	components that its blocks use."""
	view = WorkspaceView({"name": workspace})
	if not has_permission(view.doc) or not view.is_permitted():
		frappe.throw(_("You do not have access to this workspace."), frappe.PermissionError)

	root = get_root_component(view.doc)
	block = WidgetResolver(view).resolve(root["block"])
	root["block"] = frappe.as_json(block, indent=None)
	return [root, *get_components_for_blocks(block)]


@frappe.whitelist(methods=["POST"])
def make_workspace_component(workspace: str) -> str:
	"""Give a workspace a root component of its own, made from its content, so that Studio can
	edit it. Return the component's id."""
	doc = frappe.get_doc("Workspace", workspace)
	if not can_edit_workspace(doc):
		frappe.throw(_("You cannot edit this workspace."), frappe.PermissionError)
	if doc.studio_component:
		return doc.studio_component
	if doc.standard and not frappe.conf.developer_mode:
		frappe.throw(_("A standard workspace gets its component in developer mode."), title=_("Not Allowed"))

	component = frappe.new_doc("Studio Component")
	component.update(
		{
			"component_id": get_root_component_id(doc.name),
			"component_name": doc.title,
			"block": get_legacy_block(doc),
			# a standard workspace ships its component in the files of its app
			"frappe_app": frappe.db.get_value("Module Def", doc.module, "app_name") if doc.standard else None,
		}
	)
	component.insert()
	doc.studio_component = component.name
	doc.save()
	return component.name


def get_root_component(doc) -> dict:
	"""The root as a component document. An older workspace has none stored, so its root exists
	only in this reply."""
	if doc.studio_component:
		component = frappe.get_cached_doc("Studio Component", doc.studio_component)
		block, script, component_id = frappe.parse_json(component.block), component.script, component.name
	else:
		block, script, component_id = get_legacy_block(doc), None, get_root_component_id(doc.name)
	return {
		"name": component_id,
		"component_id": component_id,
		"component_name": doc.title,
		"block": block,
		"script": script,
		"inputs": [],
	}


def get_root_component_id(workspace: str) -> str:
	return f"workspace_{frappe.scrub(workspace)}"


def get_root_component_ids() -> list[str]:
	"""The components that draw a whole workspace. They are not widgets, so a picker hides them."""
	return frappe.get_all("Workspace", filters={"studio_component": ("is", "set")}, pluck="studio_component")


# LEGACY CONTENT


def get_legacy_block(doc) -> dict:
	"""The root block for a workspace that has `content` and widget tables: a grid with one
	block for each content block."""
	rows = get_widget_rows(doc)
	blocks = [get_legacy_child(item, rows) for item in frappe.parse_json(doc.content or "[]")]
	return {
		"componentId": "workspace-root",
		"componentName": "container",
		"originalElement": "div",
		"baseStyles": {
			"display": "grid",
			"gridTemplateColumns": f"repeat({GRID_COLUMNS}, minmax(0, 1fr))",
			"gap": "16px",
			"width": "100%",
		},
		"children": [block for block in blocks if block],
	}


def get_widget_rows(doc) -> dict[str, dict[str, dict]]:
	"""The rows of each widget table by their label, which is how a content block names its row."""
	return {
		"card": {card.label: get_links_props(card) for card in doc.get_link_groups()},
		"shortcut": {row.label: pick(row, SHORTCUT_FIELDS) for row in doc.shortcuts},
		"number_card": {
			row.label: {"card": row.number_card_name, "label": row.label} for row in doc.number_cards
		},
		"chart": {row.label: {"chart": row.chart_name, "label": row.label} for row in doc.charts},
		"quick_list": {
			row.label: pick(row, ("label", "document_type", "quick_list_filter")) for row in doc.quick_lists
		},
	}


def get_links_props(card) -> dict:
	return {"label": card.label, "links": [pick(link, LINK_FIELDS) for link in card.get("links", [])]}


def pick(row, fields: tuple[str, ...]) -> dict:
	return {field: row.get(field) for field in fields if row.get(field) not in (None, "")}


def get_legacy_child(item: dict, rows: dict) -> dict | None:
	"""The block for one content block. None for a type that has no component yet, and for a
	widget whose row is gone."""
	block_type, data = item.get("type"), item.get("data") or {}
	if block_type in ("header", "paragraph"):
		block = get_text_block(data.get("text"), is_header=block_type == "header")
	elif block_type == "spacer":
		block = {"componentName": "container", "originalElement": "div", "baseStyles": {"height": "8px"}}
	elif block_type in LEGACY_WIDGETS:
		component, label_key = LEGACY_WIDGETS[block_type]
		props = rows[block_type].get(data.get(label_key))
		if not props:
			return None
		block = {"componentName": component, "isStudioComponent": True, "componentProps": props}
	else:
		return None

	block["componentId"] = f"{block['componentName']}-{item.get('id') or frappe.generate_hash(length=8)}"
	columns = min(int(data.get("col") or GRID_COLUMNS), GRID_COLUMNS)
	block.setdefault("baseStyles", {})["gridColumn"] = f"span {columns}"
	block["tabletStyles"] = {"gridColumn": f"span {GRID_COLUMNS if columns > 4 else 6}"}
	block["mobileStyles"] = {"gridColumn": f"span {GRID_COLUMNS}"}
	return block


def get_text_block(html: str | None, is_header: bool) -> dict:
	styles = (
		{"color": "var(--ink-gray-8)", "fontWeight": "600"} if is_header else {"color": "var(--ink-gray-6)"}
	)
	return {
		"componentName": "TextBlock",
		"componentProps": {
			"text": strip_html(html or "").strip(),
			"fontSize": "text-lg" if is_header else "text-p-base",
		},
		"baseStyles": styles,
	}


# PERMISSIONS


class WidgetResolver:
	"""Give each widget block the props that the session user may see. A widget with nothing
	left to show is removed from the tree."""

	def __init__(self, view: WorkspaceView):
		self.view = view
		self.resolvers = {
			"desk_links": self.resolve_links,
			"desk_shortcut": self.resolve_shortcut,
			"desk_number_card": self.resolve_number_card,
			"desk_chart": self.resolve_chart,
			"desk_quick_list": self.resolve_quick_list,
		}

	def resolve(self, block: dict) -> dict | None:
		block = dict(block)
		resolver = self.resolvers.get(block.get("componentName")) if block.get("isStudioComponent") else None
		if resolver:
			props = resolver(frappe._dict(block.get("componentProps") or {}))
			if not props:
				return None
			block["componentProps"] = props
		children = [self.resolve(child) for child in block.get("children") or []]
		block["children"] = [child for child in children if child]
		return block

	def resolve_links(self, props) -> dict | None:
		country = frappe.db.get_default("country")
		links = [
			self.view._prepare_item(frappe._dict(link))
			for link in props.links or []
			if not (link.get("country") and link.get("country") != country)
			and is_item_allowed(link.get("link_to"), link.get("link_type"), self.view)
		]
		return {"label": _(props.label), "links": links} if links else None

	def resolve_shortcut(self, props) -> dict | None:
		in_domain = not props.restrict_to_domain or props.restrict_to_domain in frappe.get_active_domains()
		if not in_domain or not is_item_allowed(props.link_to, props.type, self.view):
			return None
		if props.type == "Report":
			report = self.view.allowed_reports.get(props.link_to, {})
			if report.get("report_type") in ("Query Report", "Script Report", "Custom Report"):
				props.is_query_report = 1
			else:
				props.ref_doctype = report.get("ref_doctype")
		props.label = _(props.label) if props.label else _(props.link_to)
		return props

	def resolve_number_card(self, props) -> dict | None:
		return self.resolve_record(props, "Number Card", props.card, NUMBER_CARD_FIELDS)

	def resolve_chart(self, props) -> dict | None:
		props = self.resolve_record(props, "Dashboard Chart", props.chart, CHART_FIELDS)
		if props:
			y_axis = frappe.get_cached_doc("Dashboard Chart", props.chart).y_axis
			props.doc["y_fields"] = [row.y_field for row in y_axis]
		return props

	def resolve_record(self, props, doctype: str, name: str, fields: tuple[str, ...]) -> dict | None:
		"""A widget of one record, which the user must be able to read. The widget gets the
		fields that it fetches its data with."""
		if not frappe.db.exists(doctype, name) or not frappe.has_permission(doctype, doc=name):
			return None
		doc = frappe.get_cached_doc(doctype, name)
		props.doc = {"name": name, "doctype": doctype, **pick(doc, fields)}
		props.label = _(props.label or doc.get("label") or name)
		return props

	def resolve_quick_list(self, props) -> dict | None:
		if not is_item_allowed(props.document_type, "doctype", self.view):
			return None
		props.label = _(props.label) if props.label else _(props.document_type)
		props.title_field = frappe.get_meta(props.document_type).get_title_field()
		return props
