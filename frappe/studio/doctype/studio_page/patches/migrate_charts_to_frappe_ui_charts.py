import frappe

from studio.utils import walk_blocks

CHART_MARKS = {"line": "LineChart", "area": "AreaChart"}
DEFAULT_HEIGHT = "300px"


def execute():
	skipped = []
	for page in frappe.get_all("Studio Page", fields=["name", "blocks", "draft_blocks"]):
		updates = {}
		for field in ("blocks", "draft_blocks"):
			if page.get(field):
				updated = migrate_blocks_json(page.get(field), skipped, page.name)
				if updated != page.get(field):
					updates[field] = updated
		if updates:
			frappe.db.set_value("Studio Page", page.name, updates, update_modified=False)

	for component in frappe.get_all("Studio Component", fields=["name", "block"]):
		if component.get("block"):
			updated = migrate_blocks_json(component.block, skipped, component.name)
			if updated != component.block:
				frappe.db.set_value(
					"Studio Component", component.name, "block", updated, update_modified=False
				)

	if skipped:
		print(
			"Charts with a dynamic `config` need a manual update to the frappe-ui/charts props:\n"
			+ "\n".join(f"  {doc}: {component_id}" for doc, component_id in sorted(set(skipped)))
		)


def migrate_blocks_json(value, skipped=None, docname=None):
	blocks = frappe.parse_json(value) if isinstance(value, str) else value
	for block in walk_blocks(blocks):
		if not migrate_block(block) and skipped is not None:
			skipped.append((docname, block.get("componentId")))
	return frappe.as_json(blocks, indent=None)


def migrate_block(block):
	"""Return False for an old chart whose `config` can't be migrated statically."""
	handler = HANDLERS.get(block.get("componentName"))
	if not handler:
		return True
	props = block.get("componentProps") or {}
	if "config" not in props:
		return True
	config = props.get("config")
	if not isinstance(config, dict):
		return False
	block["componentProps"] = handler(block, config) or {}
	return True


def migrate_axis_chart(block, config):
	series = [s for s in config.get("series") or [] if isinstance(s, dict) and s.get("name")]
	marks = {s.get("type") or "bar" for s in series}
	component = CHART_MARKS.get(marks.pop()) if len(marks) == 1 else None
	component = component or "BarChart"
	default_mark = {"LineChart": "line", "AreaChart": "area"}.get(component, "bar")
	block["componentName"] = component

	x_axis = config.get("xAxis") or {}
	names = [s["name"] for s in series if s.get("axis") != "y2"]
	y2_names = [s["name"] for s in series if s.get("axis") == "y2"]
	props = base_props(config)
	props.update(
		{
			"data": config.get("data"),
			"x": x_axis.get("key"),
			"y": names[0] if len(names) == 1 else names,
			"y2": y2_names[0] if len(y2_names) == 1 else y2_names,
			"xAxis": compact({k: x_axis.get(k) for k in ("type", "timeGrain", "title", "echartOptions")}),
			"yAxis": value_axis(config.get("yAxis")),
			"y2Axis": value_axis(config.get("y2Axis")),
			"stacked": config.get("stacked"),
			"seriesConfig": compact({s["name"]: series_style(s, default_mark) for s in series}),
		}
	)
	if config.get("swapXY") and component == "BarChart":
		props["horizontal"] = True
	set_default_height(block)
	return compact(props)


def migrate_donut_chart(block, config):
	props = base_props(config)
	props.update(
		{
			"data": config.get("data"),
			"category": config.get("categoryColumn"),
			"value": config.get("valueColumn"),
			"maxSlices": config.get("maxSliceCount"),
			"showDataLabels": config.get("showInlineLabels"),
		}
	)
	set_default_height(block)
	return compact(props)


def migrate_number_chart(block, config):
	block["componentName"] = "NumberCard"
	keys = ("title", "value", "prefix", "suffix", "delta", "deltaPrefix", "deltaSuffix", "negativeIsBetter")
	return compact({key: config.get(key) for key in keys})


def base_props(config):
	return {
		"title": config.get("title"),
		"subtitle": config.get("subtitle"),
		"dir": config.get("dir"),
		"palette": config.get("colors"),
		"echartOptions": config.get("echartOptions"),
	}


def value_axis(axis):
	if not isinstance(axis, dict):
		return None
	return compact(
		{
			"title": axis.get("title"),
			"min": axis.get("yMin"),
			"max": axis.get("yMax"),
			"echartOptions": axis.get("echartOptions"),
		}
	)


def series_style(series, default_mark):
	mark = series.get("type") or "bar"
	return compact(
		{
			"type": mark if mark != default_mark else None,
			"color": series.get("color"),
			"showDataLabels": series.get("showDataLabels"),
			"stackName": series.get("stackName"),
			"dashed": True if series.get("lineType") in ("dashed", "dotted") else None,
			"showDataPoints": series.get("showDataPoints"),
			"echartOptions": series.get("echartOptions"),
		}
	)


def set_default_height(block):
	# the old charts had a 300px min-height; the new ones fill their parent
	styles = block.get("baseStyles") or {}
	if not styles.get("height") and not styles.get("minHeight"):
		block["baseStyles"] = {**styles, "height": DEFAULT_HEIGHT}


def compact(values):
	return {key: value for key, value in values.items() if value not in (None, "", [], {})} or None


HANDLERS = {
	"AxisChart": migrate_axis_chart,
	"DonutChart": migrate_donut_chart,
	"NumberChart": migrate_number_chart,
}
