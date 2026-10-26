// A Number Card's value, as the desk number card widget computes it: the same three result
// endpoints, filters and formatting.

import { post } from "../api.js";

const STATS_CAPTIONS = {
	Daily: "since yesterday",
	Weekly: "since last week",
	Monthly: "since last month",
	Yearly: "since last year",
};

export async function load_card(name) {
	const frappe = window.frappe;
	const card = await frappe.model.with_doc("Number Card", name);
	if (!card.type) card.type = "Document Type";
	const filters = frappe.dashboard_utils.get_all_filters(card);

	const result = { card, filters, value: null, delta: null, caption: null };
	if (card.type === "Custom") {
		const res = await post(card.method, { filters });
		result.data = res;
		result.value = typeof res === "object" ? format_number(card, res?.value, res) : res;
	} else if (card.type === "Report") {
		const res = await post("frappe.desk.query_report.run", {
			report_name: card.report_name,
			filters,
			ignore_prepared_report: 1,
		});
		const field = card.report_field;
		const values = res.result.map((row) => row[field]).filter(Boolean);
		const df = res.columns.find((col) => col.fieldname === field);
		const number = frappe.report_utils.get_result_of_fn(card.report_function, values);
		result.value = format_number(card, number, df, common_doc(res.result));
	} else {
		const number = await post("frappe.desk.doctype.number_card.number_card.get_result", {
			doc: card,
			filters,
		});
		result.value = await format_doctype_number(card, number);
		if (card.show_percentage_stats) {
			const delta = await post(
				"frappe.desk.doctype.number_card.number_card.get_percentage_difference",
				{ doc: card, filters, result: number }
			);
			if (typeof delta === "number" && !isNaN(delta)) {
				result.delta = delta;
				result.caption = window.__(STATS_CAPTIONS[card.stats_time_interval] || "");
			}
		}
	}
	return result;
}

// How far back the trend reaches, at the card's own stats interval.
const TREND_SPANS = {
	Daily: { timespan: "Last Month" },
	Weekly: { timespan: "Last Year" },
	Monthly: { timespan: "Select Date Range", months: 24 },
	Yearly: { timespan: "Select Date Range", months: 60 },
};

// A Document Type card's value per period, drawn as its sparkline. Min and Max have no
// running series, and Report and Custom cards have no date to group on.
export async function load_trend({ card, filters }) {
	const frappe = window.frappe;
	if (card.type !== "Document Type" || !["Count", "Sum", "Average"].includes(card.function)) {
		return null;
	}

	const time_interval = card.stats_time_interval || "Weekly";
	const { timespan, months } = TREND_SPANS[time_interval];
	const today = frappe.datetime.get_today();
	const data = await post("frappe.desk.doctype.dashboard_chart.dashboard_chart.get", {
		chart: {
			chart_type: card.function,
			document_type: card.document_type,
			parent_document_type: card.parent_document_type,
			based_on: "creation",
			value_based_on: card.aggregate_function_based_on,
		},
		no_cache: 1,
		filters: [...filters],
		timespan,
		time_interval,
		from_date: months ? frappe.datetime.add_months(today, -months) : null,
		to_date: months ? today : null,
	});

	const values = data?.datasets?.[0]?.values || [];
	return values.some((value) => value) ? values : null;
}

function format_doctype_number(card, number) {
	if (card.function === "Count") return Promise.resolve(number);
	return new Promise((resolve) =>
		window.frappe.model.with_doctype(card.document_type, () => {
			const df = window.frappe.meta.get_docfield(
				card.document_type,
				card.aggregate_function_based_on
			);
			resolve(format_number(card, number, df));
		})
	);
}

function format_number(card, number, df, doc) {
	const frappe = window.frappe;
	if (number === null || number === undefined || isNaN(number)) {
		return window.__("N/A", null, "Number not available");
	}

	// a duration formats its own units, so it is never shortened
	const [value, symbol = ""] =
		card.show_full_number || df?.fieldtype === "Duration"
			? [String(number)]
			: frappe.utils.shorten_number(number, frappe.sys_defaults.country, 5).split(" ");
	const suffix = symbol ? " " + symbol : "";

	if (card.currency) return window.format_currency(parseFloat(value), card.currency) + suffix;

	const formatted = frappe.format(window.convert_old_to_new_number_format(value), df, null, doc);
	return text_of(formatted) + suffix;
}

// `frappe.format` may return markup; parsed off-document so nothing in it runs.
export function text_of(html) {
	return new DOMParser().parseFromString(String(html), "text/html").body.textContent;
}

// the fields every report row agrees on, for currency and similar formatting
function common_doc(rows) {
	if (!rows?.length) return {};
	const doc = { ...rows[0] };
	for (const row of rows) {
		if (Array.isArray(row)) continue;
		for (const key of Object.keys(doc)) {
			if (doc[key] !== row[key]) delete doc[key];
		}
	}
	return doc;
}

// Where clicking the card goes: its list or report, filtered as the card is.
export function open_card({ card, filters, data }) {
	const frappe = window.frappe;
	if (card.type === "Custom") {
		if (!data?.route) return;
		if (data.route_options) frappe.route_options = data.route_options;
		frappe.set_route(data.route);
		return;
	}

	const is_doctype = card.type !== "Report";
	const route = frappe.utils.generate_route({
		name: is_doctype ? card.document_type : card.report_name,
		type: is_doctype ? "doctype" : "report",
		is_query_report: !is_doctype,
	});
	if (is_doctype) {
		frappe.route_options = filters.reduce((options, [, field, operator, value]) => {
			(options[field] ||= []).push([operator, value]);
			return options;
		}, {});
	} else if (filters && Object.keys(filters).length) {
		frappe.route_options = filters;
	}
	frappe.set_route(route);
}
