import re

import frappe

from studio.studio.doctype.studio_page.patches.migrate_dialog_to_frappe_ui_v1 import migrate_dialog_props
from studio.utils import walk_blocks

RADIUS_SIDES = ("t", "r", "b", "l", "tl", "tr", "br", "bl", "s", "e", "ss", "se", "es", "ee")
RADIUS_STEPS = {"sm": "1", "md": "5", "lg": "6", "xl": "7", "2xl": "8"}
_RADIUS_RE = re.compile(
	r"(?<![A-Za-z0-9-])rounded(-(?:" + "|".join(RADIUS_SIDES) + r"))?(?:-(sm|md|lg|xl|2xl))?(?![A-Za-z0-9-])"
)

PLACEMENT_ALIGN = {"start": "start", "end": "end", "center": "center"}
MENU_ALIGN = {"left": "start", "right": "end", "center": "center"}
INPUT_SIZES = {"xl": "lg", "2xl": "lg"}
ICON_PROPS = ("icon", "iconLeft", "iconRight")


def execute():
	for page in frappe.get_all("Studio Page", fields=["name", "blocks", "draft_blocks"]):
		updates = {}
		for field in ("blocks", "draft_blocks"):
			if page.get(field):
				updated = migrate_blocks_json(page.get(field))
				if updated != page.get(field):
					updates[field] = updated
		if updates:
			frappe.db.set_value("Studio Page", page.name, updates, update_modified=False)

	for component in frappe.get_all("Studio Component", fields=["name", "block"]):
		if component.get("block"):
			updated = migrate_blocks_json(component.block)
			if updated != component.block:
				frappe.db.set_value(
					"Studio Component", component.name, "block", updated, update_modified=False
				)


def migrate_blocks_json(value):
	blocks = frappe.parse_json(value) if isinstance(value, str) else value
	for block in walk_blocks(blocks):
		migrate_block(block)
		migrate_classes(block)
	return frappe.as_json(blocks, indent=None)


def migrate_block(block):
	handler = HANDLERS.get(block.get("componentName"))
	if not handler:
		return
	block["componentProps"] = block.get("componentProps") or {}
	handler(block, block["componentProps"])


def migrate_classes(block):
	block["classes"] = [rename_radius(name) for name in block.get("classes") or []]
	props = block.get("componentProps") or {}
	if isinstance(props.get("class"), str):
		props["class"] = rename_radius(props["class"])


def rename_radius(text):
	def replace(match):
		side, alias = match.group(1) or "", match.group(2)
		return f"rounded{side}-{RADIUS_STEPS[alias] if alias else '4'}"

	return _RADIUS_RE.sub(replace, text)


def rename_props(props, renames):
	for old, new in renames.items():
		if old in props:
			value = props.pop(old)
			props.setdefault(new, value)


def rename_slots(block, renames):
	slots = block.get("componentSlots") or {}
	for old, new in renames.items():
		if old not in slots or new in slots:
			continue
		slot = slots.pop(old)
		slot["slotName"] = new
		if slot.get("slotId"):
			slot["slotId"] = f"{slot['slotId'].rsplit(':', 1)[0]}:{new}"
		for child in slot.get("slotContent") or []:
			if isinstance(child, dict) and child.get("parentSlotName") == old:
				child["parentSlotName"] = new
		slots[new] = slot


def rename_events(block, renames):
	events = block.get("componentEvents") or {}
	for old, new in renames.items():
		if old in events and new not in events:
			events[new] = events.pop(old)


def split_placement(props):
	placement = props.pop("placement", None)
	if not isinstance(placement, str) or not placement:
		return
	side, _, align = placement.partition("-")
	props.setdefault("side", side)
	props.setdefault("align", PLACEMENT_ALIGN.get(align, "center"))


def lucide_icon(value):
	if not isinstance(value, str) or not value or value.startswith(("lucide-", "{{")) or not value.isascii():
		return value
	return f"lucide-{value}"


def migrate_icons(props):
	for key in ICON_PROPS:
		if key in props:
			props[key] = lucide_icon(props[key])


def migrate_menu_options(options):
	for option in options if isinstance(options, list) else []:
		if not isinstance(option, dict):
			continue
		if "items" in option and "options" not in option:
			option["options"] = option.pop("items")
		migrate_icons(option)
		migrate_menu_options(option.get("options"))


def migrate_input_size(props):
	if props.get("size") in INPUT_SIZES:
		props["size"] = INPUT_SIZES[props["size"]]


def migrate_theme(props, renames):
	if props.get("theme") in renames:
		props["theme"] = renames[props["theme"]]


def migrate_autocomplete(block, props):
	block["componentName"] = "MultiSelect" if props.pop("multiple", False) else "Combobox"
	migrate_menu_options(props.get("options"))
	split_placement(props)
	for key in ("showFooter", "bodyClasses", "maxOptions"):
		props.pop(key, None)
	rename_slots(block, {"target": "trigger"})


def migrate_form_control(block, props):
	if props.get("type") == "autocomplete":
		props["type"] = "multiselect" if props.pop("multiple", False) else "combobox"
	migrate_input_size(props)


def migrate_feather_icon(block, props):
	block["componentName"] = "Icon"
	if props.get("name"):
		props["icon"] = lucide_icon(props.pop("name"))
	if props.get("color"):
		block.setdefault("baseStyles", {}).setdefault("color", props.pop("color"))
	for key in ("strokeWidth", "size", "color"):
		props.pop(key, None)


def migrate_alert(block, props):
	migrate_theme(props, {"yellow": "amber"})
	for key in ("variant", "type", "modelValue"):
		props.pop(key, None)
	rename_slots(block, {"icon": "prefix", "footer": "actions", "default": "description"})


def migrate_badge(block, props):
	migrate_theme(props, {"orange": "amber"})


def migrate_dialog(block, props):
	migrate_dialog_props(block)
	props = block["componentProps"]
	migrate_theme(props, {"yellow": "amber"})
	icon = props.get("icon")
	if isinstance(icon, dict):
		appearance = {"warning": "amber", "info": "blue", "danger": "red", "success": "green"}
		theme = icon.get("theme") or appearance.get(icon.get("appearance"))
		props["icon"] = lucide_icon(icon.get("name"))
		if theme:
			props.setdefault("theme", "amber" if theme == "yellow" else theme)
	for action in props.get("actions") or []:
		if isinstance(action, dict):
			migrate_icons(action)
	rename_slots(
		block, {"body-content": "default", "body-main": "default", "body-title": "title", "body": "default"}
	)


def migrate_popover(block, props):
	split_placement(props)
	rename_props(
		props, {"show": "open", "hideOnBlur": "dismissible", "matchTargetWidth": "matchTriggerWidth"}
	)
	for key in ("popoverClass", "transition", "trigger", "hoverDelay", "leaveDelay"):
		props.pop(key, None)
	if "body" in (block.get("componentSlots") or {}):
		props.setdefault("bare", True)
	rename_slots(block, {"target": "trigger", "body-main": "default", "body": "default"})
	rename_events(block, {"update:show": "update:open"})


def migrate_tooltip(block, props):
	rename_props(props, {"placement": "side"})
	props.pop("arrowClass", None)
	if isinstance(props.get("hoverDelay"), int | float) and props["hoverDelay"] < 10:
		props["hoverDelay"] = props["hoverDelay"] * 1000
	rename_slots(block, {"body": "content"})


def migrate_menu(block, props):
	placement = props.pop("placement", None)
	if placement in MENU_ALIGN:
		props.setdefault("align", MENU_ALIGN[placement])
	migrate_menu_options(props.get("options"))


def migrate_button(block, props):
	migrate_icons(props)
	rename_props(props, {"link": "href", "to": "route"})
	migrate_input_size(props)


def migrate_tab_buttons(block, props):
	rename_props(props, {"buttons": "options", "type": "variant", "direction": "side"})
	for option in props.get("options") or []:
		if not isinstance(option, dict):
			continue
		option.setdefault("value", option.get("label"))
		for key in ("hideLabel", "class", "tooltip", "theme", "variant", "size", "loading"):
			option.pop(key, None)
		migrate_icons(option)


def migrate_tabs(block, props):
	props.pop("as", None)
	tabs = [tab for tab in props.get("tabs") or [] if isinstance(tab, dict)]
	for tab in tabs:
		tab.setdefault("value", tab.get("label"))
		migrate_icons(tab)
	index = props.get("modelValue")
	if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(tabs):
		props["modelValue"] = tabs[index]["value"]
	rename_slots(
		block,
		{
			"tab-item": "tab-label",
			"prefix": "tab-prefix",
			"label": "tab-label",
			"suffix": "tab-suffix",
			"panel": "tab-panel",
		},
	)


def migrate_checkbox(block, props):
	rename_props(props, {"padding": "padded", "checked": "modelValue"})


def migrate_switch(block, props):
	props.pop("labelClasses", None)
	rename_events(block, {"change": "update:modelValue"})


def migrate_rating(block, props):
	rename_props(props, {"rating_from": "max", "readonly": "disabled"})


def migrate_picker(block, props):
	rename_props(
		props,
		{
			"value": "modelValue",
			"inputClass": "class",
			"minTime": "min",
			"maxTime": "max",
			"minDateTime": "min",
			"maxDateTime": "max",
		},
	)
	split_placement(props)
	if "autoClose" in props:
		props.setdefault("keepOpen", not props.pop("autoClose"))
	allow_custom = props.pop("allowCustom", None)
	readonly = props.pop("readonly", None)
	if allow_custom is not None or readonly is not None:
		props.setdefault("typeable", bool(allow_custom) and not readonly)
	if props.pop("use12Hour", False):
		props.setdefault("format", "h:mm A")
	for key in ("scrollMode", "allowCustomTime"):
		props.pop(key, None)
	if block.get("componentName") == "DateRangePicker" and isinstance(props.get("modelValue"), str):
		value = props["modelValue"]
		if value and "{{" not in value:
			props["modelValue"] = value.split(",")
	migrate_input_size(props)
	rename_slots(block, {"target": "trigger"})


def migrate_file_uploader(block, props):
	upload_args = props.pop("uploadArgs", None)
	if not isinstance(upload_args, dict):
		return
	if "private" in upload_args or "is_private" in upload_args:
		props.setdefault("private", bool(upload_args.get("private", upload_args.get("is_private"))))
	for old, new in {
		"folder": "folder",
		"doctype": "doctype",
		"docname": "docname",
		"fieldname": "fieldname",
		"upload_endpoint": "uploadEndpoint",
		"optimize": "optimize",
	}.items():
		if old in upload_args:
			props.setdefault(new, upload_args[old])


def migrate_tree(block, props):
	if "node" in props and "nodes" not in props:
		props["nodes"] = [props.pop("node")]
	options = props.pop("options", None)
	if isinstance(options, dict) and options.get("showIndentationGuides") is False:
		props.setdefault("guides", "none")
	rename_slots(block, {"node": "item", "label": "item-label"})


def migrate_settings_dialog(block, props):
	rename_props(props, {"modelValue": "open"})
	shortcut = props.pop("shortcut", None)
	if shortcut is False:
		props.setdefault("keyboardShortcut", False)


def migrate_sidebar(block, props):
	if "disableCollapse" in props:
		props.setdefault("collapsible", not props.pop("disableCollapse"))
	header = props.pop("header", None)
	sections = props.pop("sections", None)
	children = block.setdefault("children", [])
	if children:
		return
	if isinstance(header, dict) and header.get("title"):
		header_props = {key: header[key] for key in ("title", "subtitle", "menuItems") if key in header}
		migrate_menu_options(header_props.get("menuItems"))
		children.append(new_block("SidebarHeader", header_props))
	for section in sections if isinstance(sections, list) else []:
		if not isinstance(section, dict):
			continue
		if section.get("label"):
			label = new_block("SidebarLabel")
			label["children"].append(new_block("TextBlock", {"text": section["label"], "tag": "span"}))
			children.append(label)
		for item in section.get("items") or []:
			if isinstance(item, dict):
				item = dict(item)
				migrate_sidebar_item(None, item)
				children.append(new_block("SidebarItem", item))


def migrate_sidebar_item(block, props):
	rename_props(props, {"to": "route", "isActive": "active"})
	icon = props.get("icon")
	match = isinstance(icon, str) and re.fullmatch(r"\{\{\s*getIcon\(['\"]([a-z0-9-]+)['\"]\)\s*\}\}", icon)
	props["icon"] = f"lucide-{match.group(1)}" if match else lucide_icon(icon)


def migrate_sidebar_header(block, props):
	migrate_menu_options(props.get("menuItems"))
	rename_slots(block, {"logo": "prefix", "header-logo": "prefix"})


def migrate_input(block, props):
	migrate_input_size(props)
	if block.get("componentName") == "Password":
		rename_props(props, {"value": "modelValue"})


def migrate_select(block, props):
	migrate_input(block, props)
	rename_slots(block, {"option": "item-label"})


def migrate_combobox(block, props):
	migrate_input(block, props)
	split_placement(props)
	props.pop("allowCustomValue", None)
	migrate_menu_options(props.get("options"))


def migrate_multi_select(block, props):
	migrate_input(block, props)
	props.pop("compareFn", None)
	migrate_menu_options(props.get("options"))


def migrate_form_label(block, props):
	props.pop("size", None)


def migrate_keyboard_shortcut(block, props):
	rename_props(props, {"shortcut": "combo"})


def migrate_divider(block, props):
	rename_props(props, {"position": "align"})
	action = props.get("action")
	if isinstance(action, dict):
		rename_props(action, {"handler": "onClick"})


def migrate_progress(block, props):
	count = props.pop("intervalCount", None)
	if count is not None and props.get("intervals") is True:
		props["intervals"] = count


def migrate_list_row(block, props):
	rename_props(props, {"to": "route"})


def migrate_list_group(block, props):
	rename_slots(block, {"header": "label"})


def migrate_list_header_cell_sort(block, props):
	rename_slots(block, {"suffix": "sort-indicator"})


def new_block(component_name, props=None):
	return {
		"componentId": f"{component_name}-{frappe.generate_hash(length=9).lower()}",
		"componentName": component_name,
		"componentProps": props or {},
		"baseStyles": {},
		"children": [],
		"classes": [],
	}


HANDLERS = {
	"Autocomplete": migrate_autocomplete,
	"FormControl": migrate_form_control,
	"FeatherIcon": migrate_feather_icon,
	"Alert": migrate_alert,
	"Badge": migrate_badge,
	"Dialog": migrate_dialog,
	"Popover": migrate_popover,
	"Tooltip": migrate_tooltip,
	"Dropdown": migrate_menu,
	"ContextMenu": migrate_menu,
	"Button": migrate_button,
	"TabButtons": migrate_tab_buttons,
	"Tabs": migrate_tabs,
	"Checkbox": migrate_checkbox,
	"Switch": migrate_switch,
	"Rating": migrate_rating,
	"DatePicker": migrate_picker,
	"DateTimePicker": migrate_picker,
	"DateRangePicker": migrate_picker,
	"TimePicker": migrate_picker,
	"FileUploader": migrate_file_uploader,
	"Tree": migrate_tree,
	"SettingsDialog": migrate_settings_dialog,
	"Sidebar": migrate_sidebar,
	"SidebarItem": migrate_sidebar_item,
	"SidebarHeader": migrate_sidebar_header,
	"TextInput": migrate_input,
	"Textarea": migrate_input,
	"Password": migrate_input,
	"Duration": migrate_input,
	"Select": migrate_select,
	"Combobox": migrate_combobox,
	"MultiSelect": migrate_multi_select,
	"FormLabel": migrate_form_label,
	"KeyboardShortcut": migrate_keyboard_shortcut,
	"Divider": migrate_divider,
	"Progress": migrate_progress,
	"ListRow": migrate_list_row,
	"ListGroup": migrate_list_group,
	"ListHeaderCellSort": migrate_list_header_cell_sort,
}
