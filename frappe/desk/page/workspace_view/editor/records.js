// Some widgets only point at a record that holds what they show. The pane edits a copy of that
// record at `widget.record`, tiles draw the copy once `widget.record_changed` is set, and saving
// the page writes it back first.

import { post } from "../api.js";

const __ = (...args) => window.__(...args);

const plain = (values) => values.map((value) => ({ label: __(value), value }));

function fields_of(meta, fieldtypes) {
	return (meta?.fields || [])
		.filter((df) => fieldtypes.includes(df.fieldtype))
		.map((df) => ({ label: __(df.label), value: df.fieldname }));
}

const numeric_fields = (_, { meta }) => fields_of(meta, window.frappe.model.numeric_fieldtypes);
const report_numbers = (_, { report }) => report?.numeric_fields || [];

const DOCTYPE_LINKS = {
	document_type: () => ({ issingle: 0 }),
	parent_document_type: ({ parents }) => ({ name: ["in", parents || []] }),
	report_name: () => ({ report_type: ["!=", "Report Builder"] }),
};

const unless_developer = () => (window.frappe.boot.developer_mode ? [] : ["is_standard"]);

const reset_filters = (record, empty) =>
	Object.assign(record, { filters_json: empty, dynamic_filters_json: empty });

// the intervals desk's chart form offers for each timespan
const INTERVALS = {
	"Last Year": ["Quarterly", "Monthly", "Weekly", "Daily"],
	"Last Quarter": ["Monthly", "Weekly", "Daily"],
	"Last Month": ["Weekly", "Daily"],
	"Last Week": ["Daily"],
	"Select Date Range": ["Quarterly", "Monthly", "Weekly", "Daily"],
};

// Block type -> the pane's short name for the record, its doctype, the widget field that names it
// and what a new one starts with, then what the desk form script sets up, which FormLayout has no
// script for: `hidden` fields, `options` of a select, `link_filters` of a link and what runs
// `after` a field changes.
// `source_fields` are the fields that decide what `load_source` reads.
export const RECORDS = {
	number_card: {
		label: "Card",
		doctype: "Number Card",
		link: "number_card_name",
		blank: {
			type: "Document Type",
			function: "Count",
			filters_json: "[]",
			dynamic_filters_json: "[]",
			stats_time_interval: "Daily",
		},
		source_fields: ["type", "document_type", "report_name", "filters_json"],
		hidden: (card) => [
			...unless_developer(),
			"dynamic_filters_json",
			...(card.name ? [] : ["label"]),
		],
		options: {
			aggregate_function_based_on: numeric_fields,
			report_field: report_numbers,
		},
		link_filters: DOCTYPE_LINKS,
		after: {
			document_type: (card) => {
				Object.assign(card, { parent_document_type: "", aggregate_function_based_on: "" });
				reset_filters(card, "[]");
			},
			report_name: (card) => {
				card.report_field = "";
				reset_filters(card, "{}");
			},
		},
	},
	chart: {
		label: "Chart",
		doctype: "Dashboard Chart",
		link: "chart_name",
		blank: {
			chart_type: "Count",
			type: "Line",
			timeseries: 1,
			timespan: "Last Year",
			time_interval: "Monthly",
			based_on: "creation",
			filters_json: "[]",
			dynamic_filters_json: "[]",
		},
		source_fields: [
			"chart_type",
			"type",
			"document_type",
			"report_name",
			"source",
			"filters_json",
		],
		hidden: (chart, { report }) => [
			...unless_developer(),
			"dynamic_filters_json",
			"last_synced_on",
			...(chart.name ? [] : ["chart_name"]),
			...(chart.custom_options ? [] : ["custom_options"]),
			...(report?.has_chart ? [] : ["use_report_chart"]),
		],
		options: {
			based_on: (_, { meta }) => [
				{ label: __("Created On"), value: "creation" },
				{ label: __("Last Modified On"), value: "modified" },
				...fields_of(meta, ["Date", "Datetime"]),
			],
			value_based_on: numeric_fields,
			aggregate_function_based_on: numeric_fields,
			group_by_based_on: (_, { meta }) => [
				{ label: __("Created By"), value: "owner" },
				...fields_of(meta, ["Link", "Select"]),
			],
			time_interval: (chart) => plain(INTERVALS[chart.timespan] || []),
			x_field: (_, { report }) => report?.non_numeric_fields || [],
			y_field: report_numbers,
			heatmap_year: (_, { years }) => plain(years || []),
		},
		link_filters: DOCTYPE_LINKS,
		after: {
			chart_type: (chart) => {
				if (chart.chart_type !== "Custom") {
					chart.timeseries = ["Count", "Sum", "Average"].includes(chart.chart_type)
						? 1
						: 0;
				}
			},
			document_type: (chart) => {
				Object.assign(chart, {
					parent_document_type: "",
					based_on: "creation",
					value_based_on: "",
					group_by_based_on: "",
					aggregate_function_based_on: "",
				});
				reset_filters(chart, "[]");
			},
			report_name: (chart) => {
				Object.assign(chart, { x_field: "", y_axis: [], use_report_chart: 0 });
				reset_filters(chart, "{}");
			},
			source: (chart) => reset_filters(chart, "{}"),
			timespan: (chart) => {
				if (!INTERVALS[chart.timespan].includes(chart.time_interval)) {
					chart.time_interval = INTERVALS[chart.timespan][0];
				}
			},
		},
	},
	custom_block: {
		label: "Block",
		doctype: "Custom HTML Block",
		link: "custom_block_name",
		blank: { html: "", style: "", script: "" },
		hidden: () => ["preview"],
	},
	onboarding: {
		label: "Onboarding",
		doctype: "Module Onboarding",
		link: "name",
		blank: {},
		preview: async (widget) => {
			const { title, steps } = widget.record;
			widget.title = title || widget.label;
			widget.steps = await Promise.all(
				(steps || [])
					.filter((row) => row.step)
					.map(async ({ step, is_optional }) => {
						const doc = await window.frappe.model.with_doc("Onboarding Step", step);
						return { ...doc, description: doc.description || "", is_optional };
					})
			);
		},
	},
};

const copy = (doc) => JSON.parse(JSON.stringify(doc));

export function blank_record(type) {
	return copy(RECORDS[type].blank);
}

export async function load_record(type, name) {
	const { doctype } = RECORDS[type];
	await window.frappe.model.with_doctype(doctype);
	return copy(await window.frappe.model.with_doc(doctype, name));
}

// The filters a report or a custom source takes, as fields.
async function own_filters(type, record, kind) {
	const frappe = window.frappe;
	if (type === "chart") return frappe.dashboard_utils.get_filters_for_chart_type(record);
	if (kind === "Report") return frappe.report_utils.get_report_filters(record.report_name);
	return record.filters_config ? frappe.utils.eval(record.filters_config) : [];
}

// A report's columns, which it only gives once it has the filters it requires.
async function report_fields(record, own) {
	const frappe = window.frappe;
	const saved = JSON.parse(record.filters_json || "{}");
	const filters = Array.isArray(saved) ? {} : saved;
	if (own.some((df) => df.reqd && !filters[df.fieldname])) return null;
	const data = await frappe.xcall("frappe.desk.query_report.run", {
		report_name: record.report_name,
		filters,
		ignore_prepared_report: 1,
	});
	if (!data?.result?.length) return null;
	return {
		...frappe.report_utils.get_field_options_from_report(data.columns, data),
		has_chart: Boolean(data.chart),
	};
}

// What a record's fields are offered: the meta of the doctype it counts, the parents a child
// table can be counted under, and the filters and columns of its report or custom source.
export async function load_source(type, record) {
	const frappe = window.frappe;
	const kind = record.chart_type || record.type;
	const source = {};
	if (record.document_type && kind !== "Report") {
		await frappe.model.with_doctype(record.document_type);
		source.meta = frappe.get_meta(record.document_type);
		source.parents = source.meta.istable
			? await frappe.xcall(
					"frappe.desk.doctype.dashboard_chart.dashboard_chart.get_parent_doctypes",
					{ child_type: record.document_type }
			  )
			: [];
	}
	if ((kind === "Report" && record.report_name) || kind === "Custom") {
		source.filters = (await own_filters(type, record, kind)) || [];
	}
	if (kind === "Report" && record.report_name) {
		source.report = await report_fields(record, source.filters);
	}
	if (type === "chart" && record.type === "Heatmap") {
		const { creation } = await frappe.db.get_doc("System Settings");
		source.years = frappe.dashboard_utils.get_years_since_creation(creation);
	}
	return source;
}

export function can_edit(type, record) {
	const frappe = window.frappe;
	const { doctype } = RECORDS[type];
	if (!record.name) return frappe.model.can_create(doctype);
	if (record.is_standard && !frappe.boot.developer_mode) return false;
	return frappe.perm.has_perm(doctype, 0, "write", record);
}

async function free_name(doctype, label) {
	let name = label;
	for (let n = 2; await window.frappe.db.exists(doctype, name); n++) name = `${label} ${n}`;
	return name;
}

// A new record is named after the widget, unless that is its doctype's name, which Frappe
// refuses. Number Card numbers its own name when it is taken.
async function name_new(type, record, label) {
	const { doctype } = RECORDS[type];
	const name = label === doctype ? `${label} 1` : label;
	if (type === "number_card") record.label = name;
	else if (type === "chart") record.chart_name = await free_name(doctype, name);
	else record.name = await free_name(doctype, name);
}

// Writes a widget's edited record and points the widget at it.
export async function save_record(type, widget) {
	if (!widget.record_changed) return;
	const { doctype, link } = RECORDS[type];
	const doc = { doctype, ...widget.record };
	const method = doc.name ? "save" : "insert";
	if (!doc.name) await name_new(type, doc, doc.title || widget.label);
	const saved = await post(`frappe.client.${method}`, { doc });
	window.frappe.model.sync(copy(saved));
	widget[link] = saved.name;
	widget.record = saved;
	widget.record_changed = false;
}
