// A Dashboard Chart's data and config, as the desk chart widget builds them: the same endpoints,
// the same saved settings and the same frappe-charts config, which the `frappe.chart` island
// converts.

import { post } from "../api.js";

const CHART_TYPES = {
	Line: "line",
	Bar: "bar",
	Percentage: "percentage",
	Pie: "pie",
	Donut: "donut",
	Heatmap: "heatmap",
};

export const TIME_INTERVALS = ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"];
export const TIMESPANS = ["Last Year", "Last Quarter", "Last Month", "Last Week"];
export const DATE_RANGE = "Select Date Range";

// The chart document and the method its data comes from.
export async function load_chart(name) {
	const frappe = window.frappe;
	const doc = await frappe.model.with_doc("Dashboard Chart", name);
	if (doc.type === "Heatmap" && !doc.heatmap_year) {
		doc.heatmap_year = frappe.dashboard_utils.get_year(frappe.datetime.now_date());
	}
	return { doc, method: await data_method(doc), island: doc.__onload?.island };
}

async function data_method(doc) {
	const frappe = window.frappe;
	if (doc.chart_type === "Report") return "frappe.desk.query_report.run";
	if (doc.chart_type !== "Custom")
		return "frappe.desk.doctype.dashboard_chart.dashboard_chart.get";

	// a custom source registers itself by evaluating its config in desk
	if (!frappe.dashboards.chart_sources[doc.source]) {
		const config = await frappe.xcall(
			"frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config",
			{ name: doc.source }
		);
		frappe.dom.eval(config);
	}
	return frappe.dashboards.chart_sources[doc.source].method;
}

// The filters the chart draws with: the user's saved ones, else the chart's own.
export async function initial_filters(doc, settings) {
	const frappe = window.frappe;
	let saved = frappe.dashboard_utils.get_all_filters(doc);
	if (doc.chart_type === "Report") {
		const report_filters = await frappe.dashboard_utils.get_filters_for_chart_type(doc);
		for (const f of report_filters || []) {
			if (["Date", "DateRange"].includes(f.fieldtype) && f.default) {
				if (f.reqd || saved[f.fieldname]) saved[f.fieldname] = f.default;
			}
		}
	}
	return frappe.utils.parse_array(settings.filters) || frappe.utils.parse_array(saved);
}

export async function fetch_data({ doc, method }, filters, settings) {
	if (doc.chart_type === "Report") {
		const result = await post(method, {
			report_name: doc.report_name,
			filters,
			ignore_prepared_report: 1,
		});
		return { data: report_chart_data(doc, result), result, summary: result.report_summary };
	}
	const data = await post(method, {
		chart_name: doc.name,
		filters,
		refresh: 1,
		time_interval: settings.time_interval || null,
		timespan: settings.timespan || null,
		from_date: settings.from_date || null,
		to_date: settings.to_date || null,
		heatmap_year: settings.heatmap_year || null,
	});
	return { data };
}

function report_chart_data(doc, result) {
	const frappe = window.frappe;
	if (result.chart && doc.use_report_chart) return result.chart.data;

	const columns = result.columns.map((col) =>
		frappe.report_utils.prepare_field_from_column(col)
	);
	return frappe.report_utils.make_chart_options(columns, result, {
		y_fields: doc.y_axis.map((row) => row.y_field),
		x_field: doc.x_field,
		chart_type: doc.type,
		color: doc.color,
	}).data;
}

export function has_data(doc, data) {
	if (!data?.labels || !Object.keys(data).length) return false;
	if (doc.type === "Heatmap") return true;
	// a period with nothing in it comes back as zeroes, which would draw bare axes
	return (data.datasets || []).some((set) => (set.values || []).some((v) => window.flt(v)));
}

export async function chart_config({ doc }, data, result, settings, height) {
	const frappe = window.frappe;
	const source_doctype = await get_source_doctype(doc);
	if (source_doctype)
		await new Promise((resolve) => frappe.model.with_doctype(source_doctype, resolve));

	const args = {
		data: { ...data },
		type: CHART_TYPES[doc.type],
		colors: chart_colors(doc),
		height,
		maxSlices: doc.number_of_groups || (["Pie", "Donut"].includes(doc.type) ? 6 : 9),
		truncateLegends: 1,
		axisOptions: { xIsSeries: doc.timeseries, shortenYAxisNumbers: 1 },
	};

	let fieldtype, options;
	if (source_doctype && doc.document_type) {
		const field = frappe
			.get_meta(source_doctype)
			.fields.find((df) => df.fieldname === doc.value_based_on);
		fieldtype = field?.fieldtype;
		options = field?.options;
	}
	if (doc.chart_type === "Report" && result?.chart?.fieldtype) {
		({ fieldtype, options } = result.chart);
	}
	if (doc.chart_type === "Custom" && doc.custom_options) {
		({ fieldtype, options } = JSON.parse(doc.custom_options));
	}

	if (doc.currency) {
		if (!counts_documents(doc)) args.currency = doc.currency;
	} else {
		Object.assign(args, { fieldtype, options });
	}

	if (doc.type === "Heatmap") {
		const year = parseInt(settings.heatmap_year || doc.heatmap_year);
		args.data.start = new Date(year, 0, 1);
		args.data.end = new Date(year, 11, 31);
	}
	if (doc.show_values_over_chart) args.valuesOverPoints = true;
	if (doc.custom_options) merge_options(args, JSON.parse(doc.custom_options));

	return frappe.utils.get_chart_args(args);
}

async function get_source_doctype(doc) {
	if (doc.document_type) return doc.document_type;
	if (doc.chart_type === "Report" && doc.report_name) {
		const r = await window.frappe.db.get_value("Report", doc.report_name, "ref_doctype");
		return r.message.ref_doctype;
	}
}

function merge_options(args, custom) {
	for (const [key, value] of Object.entries(custom)) {
		args[key] =
			typeof args[key] === "object" && typeof value === "object"
				? Object.assign(args[key], value)
				: value;
	}
}

// a count is never an amount, whatever currency the chart is set to
function counts_documents({ chart_type, group_by_type }) {
	return chart_type === "Count" || (chart_type === "Group By" && group_by_type === "Count");
}

// One colour per series. A series without its own takes the palette's colour for its place.
function chart_colors(doc) {
	let colors = [];
	if (doc.y_axis?.length) colors = doc.y_axis.map((row) => row.color);
	else if (["Line", "Bar"].includes(doc.type)) colors = [doc.color];
	if (!colors.some(Boolean)) return [];

	const palette = window.frappe.utils.get_chart_palette();
	return colors.map((color, i) => color || palette[i % palette.length]);
}

let user_settings = null;

export async function save_settings(doc, settings, reset = 0) {
	// a user's settings row is made the first time desk asks for it
	user_settings ||= window.frappe.dashboard_utils.get_dashboard_settings();
	await user_settings;
	return post("frappe.desk.doctype.dashboard_settings.dashboard_settings.save_chart_config", {
		reset,
		config: settings,
		chart_name: doc.chart_name,
	});
}

export function export_csv(doc, data) {
	const rows = [[doc.chart_name], [], []];
	const datasets = data?.datasets || [];
	const labels = (data?.labels || []).map((label) => label || "None");
	if (datasets.length > 1) {
		const header = [];
		const values = [];
		labels.forEach((label, i) => {
			for (const set of datasets) {
				header.push(`${set.name} (${label})`);
				values.push(set.values?.[i] ?? "");
			}
		});
		rows.push(["", ...header], ["", ...values]);
	} else if (datasets.length === 1 && datasets[0].values?.length) {
		rows.push(["", ...labels], ["", ...datasets[0].values]);
	} else {
		rows.push(["", ...labels]);
	}
	window.frappe.tools.downloadify(rows, null, doc.chart_name);
}
