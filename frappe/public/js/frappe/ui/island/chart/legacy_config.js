/**
 * A frappe-charts config, converted to the frappe-ui chart config `frappe.chart` draws.
 *
 * The one place desk reads the legacy shape (`data.labels` / `data.datasets`, heatmap
 * `data.dataPoints`). Pure: no DOM, no `frappe`. See
 * ui/island/decisions/0016-desk-charts-are-frappe-ui-charts.md.
 */

// frappe-charts draws at this height when a config names none
const DEFAULT_HEIGHT = 240;

// frappe-charts' preset names, as the frappe-ui categorical slot of the same hue. frappe-ui's
// ramp holds five hue families, each a dark slot then its light partner.
const NAMED_COLORS = {
	blue: 1,
	"light-blue": 2,
	cyan: 2,
	"light-cyan": 2,
	green: 3,
	teal: 3,
	"light-green": 4,
	"light-teal": 4,
	purple: 5,
	violet: 5,
	"light-purple": 6,
	"light-violet": 6,
	orange: 7,
	"light-orange": 8,
	yellow: 8,
	"light-yellow": 8,
	red: 9,
	"light-red": 10,
	pink: 10,
	"light-pink": 10,
};

const GRAY_COLORS = {
	grey: "var(--ink-gray-4)",
	gray: "var(--ink-gray-4)",
	"light-grey": "var(--ink-gray-2)",
	"light-gray": "var(--ink-gray-2)",
};

// Every key the adapter reads or knowingly drops. Anything else is reported.
const KNOWN_KEYS = {
	"": [
		"type",
		"data",
		"colors",
		"height",
		"title",
		"truncateLegends",
		"maxSlices",
		"valuesOverPoints",
		"animate",
		"axisOptions",
		"barOptions",
		"lineOptions",
		"tooltipOptions",
		"discreteDomains",
		"radius",
		"countLabel",
		"count_label",
		"start",
		"end",
		"fieldtype",
		"options",
		"currency",
		// what desk's "Set Chart" dialog and the goal graph send along
		"x_field",
		"y_fields",
		"y_axis_fields",
		"chart_type",
		"summary",
	],
	data: ["labels", "datasets", "yMarkers", "dataPoints", "start", "end"],
	"data.datasets[]": ["name", "values", "chartType", "type", "color", "formatted"],
	"data.yMarkers[]": ["label", "value", "lineType", "options"],
	barOptions: ["stacked", "spaceRatio", "horizontal"],
	lineOptions: ["regionFill", "hideDots", "spline"],
	axisOptions: [
		"xIsSeries",
		"shortenYAxisNumbers",
		"xAxisMode",
		"numberFormatter",
		"seriesLabelSpaceRatio",
	],
};

const CONVERTERS = {
	bar: axis_chart,
	line: axis_chart,
	"axis-mixed": axis_chart,
	pie: slice_chart,
	donut: slice_chart,
	percentage: percentage_chart,
	heatmap: calendar_heatmap_chart,
};

/** A frappe-ui config carries its rows as an array. Anything else with `data` is legacy. */
export function is_legacy_chart_config(config) {
	return Boolean(config?.data) && !Array.isArray(config.data);
}

/**
 * @param {Object} legacy  a frappe-charts config
 * @param {{ today?: Date, center_label?: string, on_unknown_key?: (path: string) => void }} [options]
 *        `today` anchors a heatmap that names no range, as frappe-charts does.
 *        `center_label` captions a donut's total, translated by the caller.
 * @returns {Object} a frappe-ui chart config
 */
export function from_legacy_config(
	legacy,
	{ today = new Date(), center_label = "Total", on_unknown_key } = {}
) {
	if (on_unknown_key) report_unknown_keys(legacy, on_unknown_key);

	// frappe-charts' own default
	const type = legacy.type || "line";
	const convert = CONVERTERS[type];
	if (!convert) {
		throw new Error(`Unknown chart type "${type}"`);
	}

	return without_undefined({
		...convert(legacy, { today, center_label }),
		title: legacy.title || undefined,
		height: legacy.height || DEFAULT_HEIGHT,
		...format_keys(legacy),
	});
}

function axis_chart(legacy) {
	const { labels = [], datasets = [], yMarkers } = legacy.data;
	const bar_options = legacy.barOptions || {};
	const line_options = legacy.lineOptions || {};
	const colors = legacy.colors || [];
	const keys = datasets.map((_, i) => `series_${i + 1}`);

	const line_mark = line_options.regionFill ? "area" : "line";
	const default_mark = legacy.type === "bar" ? "bar" : line_mark;
	const marks = datasets.map((dataset) => {
		const mark = dataset.chartType || dataset.type || default_mark;
		return mark === "line" ? line_mark : mark;
	});
	const chart_mark = marks.length && marks.every((mark) => mark === marks[0]) ? marks[0] : null;
	const type = chart_mark || (marks.length ? "bar" : default_mark);

	const seriesConfig = {};
	datasets.forEach((dataset, i) => {
		seriesConfig[keys[i]] = without_undefined({
			label: dataset.name,
			color: to_color(dataset.color || colors[i]),
			type: marks[i] === type ? undefined : marks[i],
		});
	});

	// frappe-charts places a label by its position and frappe-ui by its value, which would draw
	// two rows sharing a label as one. A series axis keeps its labels, which read as time when
	// they are dates.
	const is_series = Boolean(legacy.axisOptions?.xIsSeries);
	const x = is_series ? "label" : "position";

	return {
		type,
		data: labels.map((label, row) => {
			const values = { [x]: is_series ? label : row };
			datasets.forEach((dataset, i) => (values[keys[i]] = to_number(dataset.values?.[row])));
			return values;
		}),
		x,
		y: keys,
		seriesConfig,
		xAxis: is_series
			? undefined
			: { type: "category", format: (row) => String(labels[row] ?? "") },
		// frappe-charts stacks bars only
		stacked: bar_options.stacked && marks.includes("bar") ? true : undefined,
		horizontal: bar_options.horizontal && type === "bar" ? true : undefined,
		smooth: line_options.spline ? true : undefined,
		showDataLabels: legacy.valuesOverPoints ? true : undefined,
		referenceLines: yMarkers?.length ? yMarkers.map(to_reference_line) : undefined,
	};
}

function slice_chart(legacy, { center_label }) {
	const { labels = [], datasets = [] } = legacy.data;
	const colors = legacy.colors || [];
	// frappe-ui orders slices by size and colors them in that order. Sorting here first
	// keeps each legacy colour on the label it was given for.
	const slices = labels
		.map((label, i) => ({
			label,
			value: total_at(datasets, i),
			color: palette_color(colors, i),
		}))
		.sort((a, b) => b.value - a.value);

	const name = datasets.length === 1 ? datasets[0].name : undefined;
	const value = name && name !== "label" ? name : "value";

	return {
		type: "donut",
		data: slices.map((slice) => ({ label: slice.label, [value]: slice.value })),
		category: "label",
		value,
		centerLabel: center_label,
		maxSlices: legacy.maxSlices || undefined,
		palette: colors.length ? slices.map((slice) => slice.color) : undefined,
	};
}

/** One bar split into a share per label: what frappe-charts' percentage chart draws. */
function percentage_chart(legacy) {
	const { labels = [], datasets = [] } = legacy.data;
	const colors = legacy.colors || [];

	const seriesConfig = {};
	labels.forEach((label, i) => {
		if (colors[i]) seriesConfig[label] = { color: to_color(colors[i]) };
	});

	return {
		type: "bar",
		data: labels.map((label, i) => ({
			label: "",
			category: label,
			value: total_at(datasets, i),
		})),
		x: "label",
		y: "value",
		splitBy: "category",
		maxSeries: legacy.maxSlices || undefined,
		seriesConfig: colors.length ? seriesConfig : undefined,
		stacked: "normalized",
		horizontal: true,
	};
}

function calendar_heatmap_chart(legacy, { today }) {
	const data = legacy.data;
	const value = legacy.countLabel || legacy.count_label || "value";
	const start = data.start || legacy.start;
	const end = data.end || legacy.end;

	// frappe-charts draws the year up to today when no range is given
	const year_ago = new Date(today);
	year_ago.setFullYear(year_ago.getFullYear() - 1);

	return {
		type: "calendar-heatmap",
		data: Object.entries(data.dataPoints || {}).map(([day, count]) => ({
			date: to_day(day),
			[value]: to_number(count),
		})),
		date: "date",
		value,
		start: to_iso_date(start || year_ago),
		end: to_iso_date(end || today),
		palette: legacy.colors?.length ? legacy.colors.map(to_color) : undefined,
	};
}

/** `currency` names the currency a `Currency` value is in. The config is the doc its options read. */
export function format_keys({ fieldtype, options, currency }) {
	if (!currency) return { fieldtype, options };
	const currency_fieldtype = fieldtype || "Currency";
	return {
		fieldtype: currency_fieldtype,
		options: options || (currency_fieldtype === "Currency" ? "currency" : undefined),
		currency,
	};
}

function to_reference_line(marker) {
	return without_undefined({
		value: marker.value,
		label: marker.label,
		dashed: marker.lineType === "dashed" || undefined,
	});
}

/** Each label's total across datasets, as frappe-charts' pie, donut and percentage sum it. */
function total_at(datasets, i) {
	return datasets.reduce((total, dataset) => total + (to_number(dataset.values?.[i]) || 0), 0);
}

/** frappe-charts draws a missing or non-numeric value as 0, and keeps a null as a gap. */
function to_number(value) {
	if (value === null) return null;
	const number = Number(value);
	return Number.isNaN(number) ? 0 : number;
}

/** A label past the end of a legacy list takes frappe-ui's own slot for its place. */
function palette_color(colors, i) {
	return to_color(colors[i]) || `var(--chart-categorical-${(i % 10) + 1})`;
}

function to_color(color) {
	if (!color) return undefined;
	const name = String(color).trim().toLowerCase();
	if (NAMED_COLORS[name]) return `var(--chart-categorical-${NAMED_COLORS[name]})`;
	return GRAY_COLORS[name] || color;
}

/** A heatmap key: unix seconds, read in the browser's zone as frappe-charts reads it, or a day. */
function to_day(key) {
	return parseInt(key) > 1e5 ? to_iso_date(new Date(key * 1000)) : key;
}

function to_iso_date(value) {
	if (!(value instanceof Date)) return value;
	const pad = (number) => String(number).padStart(2, "0");
	return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

function report_unknown_keys(legacy, on_unknown_key) {
	const check = (object, path) => {
		if (!object || typeof object !== "object") return;
		const known = KNOWN_KEYS[path];
		for (const [key, value] of Object.entries(object)) {
			// a function never survives into JSON, so no frappe-ui config can carry one
			if (typeof value === "function" || known.includes(key)) continue;
			on_unknown_key(path ? `${path}.${key}` : key);
		}
	};

	check(legacy, "");
	check(legacy.data, "data");
	legacy.data?.datasets?.forEach((dataset) => check(dataset, "data.datasets[]"));
	legacy.data?.yMarkers?.forEach((marker) => check(marker, "data.yMarkers[]"));
	for (const path of ["barOptions", "lineOptions", "axisOptions"]) check(legacy[path], path);
}

function without_undefined(object) {
	return Object.fromEntries(Object.entries(object).filter(([, value]) => value !== undefined));
}
