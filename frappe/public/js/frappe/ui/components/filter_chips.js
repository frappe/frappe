import { fill, SETTLE, still } from "./filter_chip.js";
import * as pickers from "./filter_pickers.js";
import { advanced_notice, icon_of, period_label, scroll_cue } from "./filter_pickers.js";
import {
	can_be_empty,
	duration_text,
	hook_conditions,
	is_blank,
	is_tree,
	kind_of,
	list_of,
	same_field,
	stars_of,
	std_field,
	strip_like,
	value_label,
} from "./filter_utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} FilterChipsOpts
 * @property {string} doctype The DocType being filtered; Link searches run for it.
 * @property {Object[]} [fields] Quick filters, always on the bar: DocFields ({ fieldname, label,
 *   fieldtype, options, icon }), each with the `doctype` it belongs to when that isn't `doctype`
 *   above (a desk DocField's own `doctype` is "DocField", so pass it). A text field's chip is a box
 *   typed into, as the ID search is; `typed: false` gives it a picker instead.
 * @property {Array[]} [filters] The filters to start with: [doctype, fieldname, condition, value].
 * @property {function} [onchange] Called with every filter after a chip changes one.
 * @property {function} [on_advanced] Called with (doctype, fieldname) for a filter the pickers
 *   can't show, such as two conditions on one field; the host opens its own editor for it.
 * @property {function} [get_field] Called with (doctype, fieldname) for a filtered field that
 *   isn't a quick filter; returns its DocField. Defaults to the DocType's meta.
 * @property {Object} [conditions] { key: "=" | "like" }: how a text field matches when nothing
 *   is set yet, as the person last chose it. The key is the fieldname, or "Table.fieldname" for
 *   a child table's field.
 * @property {function} [on_condition] Called with (key, condition) when that choice changes.
 * @property {function} [onopen] Called with the field when its chip's picker opens.
 *
 * A field may also carry `get_query` (as a Link field does) to narrow its records, and
 * `counts: true` to list its values with how many records have each.
 */

// one sentence each ({0} the field, {1} the value), so a language keeps its own word order
const WORDS = {
	values: {
		"=": "",
		in: "",
		"!=": () => __("{0} is not {1}"),
		"not in": () => __("{0} is not {1}"),
		"descendants of (inclusive)": "",
		like: "",
		"not like": () => __("{0} is not {1}"),
		is: "",
	},
	date: {
		Between: "",
		Timespan: "",
		is: "",
		"=": () => __("{0} on {1}"),
		"<": () => __("{0} before {1}"),
		">": () => __("{0} after {1}"),
		"<=": () => __("{0} on or before {1}"),
		">=": () => __("{0} on or after {1}"),
	},
	number: {
		Between: "",
		"=": "",
		"!=": () => __("{0} not equals {1}"),
		">": () => __("{0} more than {1}"),
		"<": () => __("{0} less than {1}"),
		">=": () => __("{0} at least {1}"),
		"<=": () => __("{0} at most {1}"),
		is: "",
	},
	text: {
		like: () => __("{0} contains {1}"),
		"not like": () => __("{0} doesn't contain {1}"),
		"=": "",
		"!=": () => __("{0} not equals {1}"),
		is: "",
	},
	check: { "=": "" },
};
const PLAIN = () => __("{0}: {1}");
const NAMED = () => __("{0} {2} {1}", null, "Filter chip: field, condition, value");

// a condition the chips have no words for (set in Advanced filters) reads with its name there; a
// sign (">=") reads the same in every language
let filter_words;
function condition_name(condition) {
	if (!/\p{L}/u.test(condition)) return condition;
	if (!filter_words) {
		filter_words = Object.create(frappe.ui.Filter.prototype);
		filter_words.set_conditions();
	}
	return filter_words.get_condition_label(condition);
}

/** The conditions a field's picker can show; any other is edited in the host's own editor. */
function picker_conditions(df) {
	let conditions;
	if (is_tree(df)) conditions = ["=", "descendants of (inclusive)", "is"];
	// Assigned To, Liked By and Tags hold a list as text, so one value matches with like
	else if (df.match === "like") conditions = ["like", "not like", "is"];
	else {
		const kind = kind_of(df);
		conditions = Object.keys(WORDS[kind]);
		if (kind === "values") conditions = conditions.filter((c) => !c.includes("like"));
		if (kind === "date") conditions.push(...hook_conditions(df));
	}
	return can_be_empty(df) ? conditions : conditions.filter((c) => c !== "is");
}

const is_contains = (value) => /^%.*%$/.test(String(value));

// people the desk hasn't loaded (a website user, say) are looked up once, so a chip reads their
// name rather than their email after a reload
const asked_names = new Set();
function name_people(users, on_found) {
	const missing = users.filter(
		(u) =>
			u &&
			!asked_names.has(u) &&
			!frappe.boot.user_info?.[u] &&
			!frappe.utils.get_link_title("User", u)
	);
	if (!missing.length) return;
	missing.forEach((u) => asked_names.add(u));
	frappe
		.xcall("frappe.client.get_list", {
			doctype: "User",
			filters: { name: ["in", missing] },
			fields: ["name", "full_name"],
			limit_page_length: missing.length,
		})
		.then((found) => {
			const named = found.filter((u) => u.full_name);
			named.forEach((u) => frappe.utils.add_link_title("User", u.name, u.full_name));
			if (named.length) on_found();
		})
		.catch(() => {});
}
const box_holds = (rules) =>
	rules.length === 1 &&
	(rules[0][0] === "=" || (rules[0][0] === "like" && is_contains(rules[0][1])));

// the date picker holds whole days; a time of day is shown as it is and edited in Advanced
function whole_days([condition, value]) {
	if (["Timespan", "is"].includes(condition)) return true;
	if (frappe.boot.additional_filters_config?.[condition]) return true;
	const values = condition === "Between" ? list_of(value) : [value];
	return values.every((v) => is_blank(v) || /^\d{4}-\d{2}-\d{2}$/.test(String(v)));
}

// a Datetime day is the person's own: it starts at their midnight, sent in the system's time
// zone as the desk stores it; whole minutes, so a time format without seconds keeps it
const midnight = (day) => frappe.datetime.convert_to_system_tz(`${day} 00:00:00`);
const next_day = (day) => frappe.datetime.add_days(day, 1);
// the person's day that a stored time starts, or null when it isn't their midnight
function day_starting(value) {
	const local = frappe.datetime.convert_to_user_tz(value);
	return /^\d{4}-\d{2}-\d{2} 00:00:00/.test(local) ? local.slice(0, 10) : null;
}

/**
 * A picker's rules as filters the host's rows and the server can hold: they have no Between for
 * numbers or for a range open at one end, and a Datetime day runs from one of the person's
 * midnights to the next. `from_rules` reads them back.
 */
function to_rules(df, rules) {
	if (df.fieldtype === "Time") return rules.map(time_rule);
	const kind = kind_of(df);
	if (kind !== "number" && kind !== "date") return rules;
	if (df.fieldtype === "Datetime") return rules.flatMap(datetime_rules);
	return rules.flatMap(([condition, value]) => {
		if (condition !== "Between" || !Array.isArray(value)) return [[condition, value]];
		const [from, to] = value;
		if (kind === "date" && !is_blank(from) && !is_blank(to)) return [[condition, value]];
		return [...(is_blank(from) ? [] : [[">=", from]]), ...(is_blank(to) ? [] : [["<=", to]])];
	});
}

// the server matches a time whole, with its seconds: "9:5" or "10:15" is sent as "10:15:00"
function time_rule([condition, value]) {
	const parts =
		["=", "!="].includes(condition) && /^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/.exec(value);
	if (!parts) return [condition, value];
	const time = parts.slice(1, 4).map((n) => String(n || 0).padStart(2, "0"));
	return [condition, time.join(":")];
}

function datetime_rules([condition, value]) {
	if (condition === "Between" && Array.isArray(value)) {
		const [from, to] = value;
		return [
			...(is_blank(from) ? [] : [[">=", midnight(from)]]),
			...(is_blank(to) ? [] : [["<", midnight(next_day(to))]]),
		];
	}
	const day = String(value);
	if (condition === "=")
		return [
			[">=", midnight(day)],
			["<", midnight(next_day(day))],
		];
	if (condition === "<" || condition === ">=") return [[condition, midnight(day)]];
	if (condition === ">") return [[">=", midnight(next_day(day))]];
	if (condition === "<=") return [["<", midnight(next_day(day))]];
	return [[condition, value]];
}

/** A field's filters as its picker shows them, the other way round from `to_rules`. */
function from_rules(df, rules) {
	const kind = kind_of(df);
	if (kind !== "number" && kind !== "date") return rules;
	if (df.fieldtype === "Datetime") return datetime_from_rules(rules);
	const from = rules.find(([condition]) => condition === ">=");
	const to = rules.find(([condition]) => condition === "<=");
	if (rules.length === 2 && from && to) {
		// a span that ends before it starts is no range: it stays as two conditions
		const after = kind === "number" ? Number(from[1]) > Number(to[1]) : from[1] > to[1];
		return after ? rules : [["Between", [from[1], to[1]]]];
	}
	return rules;
}

function datetime_from_rules(rules) {
	const from = rules.find(([condition]) => condition === ">=");
	const until = rules.find(([condition]) => condition === "<");
	if (rules.length === 2 && from && until) {
		const [first, after] = [day_starting(from[1]), day_starting(until[1])];
		if (!first || !after) return rules;
		const last = frappe.datetime.add_days(after, -1);
		// an empty span ("from 6 Nov, before 6 Nov") is no range: it stays as two conditions
		if (last < first) return rules;
		return first === last ? [["=", first]] : [["Between", [first, last]]];
	}
	if (rules.length !== 1) return rules;
	const [condition, value] = rules[0];
	const day = [">=", "<"].includes(condition) && day_starting(value);
	return day ? [[condition, day]] : rules;
}

const has_time = (value) => / \d{2}:\d{2}/.test(String(value));

// a Datetime value with a time of day shows it, as the person's own clock reads it; midnight is
// left out only where it starts a whole day, as day filters are saved (">=" and "<")
function day_text(value, timed = false, day_start = true) {
	const local =
		timed && has_time(value)
			? frappe.datetime.convert_to_user_tz(value, false)
			: moment(value);
	const day = short_day(local, local.year() !== moment().year());
	const at_midnight = local.format("HH:mm:ss") === "00:00:00";
	const time = timed && has_time(value) && !(at_midnight && day_start);
	return time ? `${day}, ${local.format("HH:mm")}` : day;
}

function range_text(from, to, timed = false) {
	if (!from) return __("until {0}", [day_text(to, timed)]);
	if (!to) return __("from {0}", [day_text(from, timed)]);
	if (timed && [from, to].some(has_time)) {
		return span(day_text(from, true), day_text(to, true));
	}
	const [a, b] = [moment(from), moment(to)];
	if (a.isSame(b, "day")) return day_text(from);
	const year = b.year() === moment().year() ? "" : ` ${b.year()}`;
	if (a.isSame(b, "month")) {
		const month = month_name(b);
		return month_first()
			? `${month} ${span(a.date(), b.date())}${year}`
			: `${span(a.date(), b.date())} ${month}${year}`;
	}
	if (a.isSame(b, "year")) return `${span(short_day(a), short_day(b))}${year}`;
	return span(short_day(a, true), short_day(b, true));
}

const span = (from, to) => __("{0} – {1}", [from, to], "a range of dates");
const month_name = (day) => frappe.ui.form.get_datepicker_locale().monthsShort[day.month()];
// "3 Mar", or "Mar 3" where the person's date format puts the month first
const month_first = () => /^m/i.test(frappe.datetime.get_user_date_fmt());

function short_day(day, with_year = false) {
	const date = month_first()
		? `${month_name(day)} ${day.date()}`
		: `${day.date()} ${month_name(day)}`;
	if (!with_year) return date;
	return month_first() ? `${date}, ${day.year()}` : `${date} ${day.year()}`;
}

function number_text(df, raw) {
	// stored as a number or plain "2.5", not in the site's number format
	const value = Number(raw);
	if (df.fieldtype === "Percent")
		return frappe.form.formatters.Percent(value, df, { only_value: true });
	if (df.fieldtype === "Rating") return `${stars_of(df, value)} ★`;
	if (df.fieldtype === "Duration") return duration_text(value);
	if (df.fieldtype === "Currency") {
		const precision = value % 1 ? undefined : 0;
		return format_currency(value, frappe.defaults.get_default("currency"), precision);
	}
	return format_number(value, null, df.fieldtype === "Int" ? 0 : undefined);
}

function value_text(df, condition, value) {
	const kind = kind_of(df);
	if (kind === "values") {
		const values = condition.includes("like") ? [strip_like(value)] : list_of(value);
		const labels = values.map((v) => value_label(df, v));
		// "is not Draft or On Hold": with "or", it's plain that both are left out
		if (labels.length === 2 && condition === "not in") return __("{0} or {1}", labels);
		return labels.join(", ");
	}
	if (kind === "check") return cint(value) ? __("Yes") : __("No");
	if (kind === "text") return `“${condition.includes("like") ? strip_like(value) : value}”`;
	if (kind === "date") {
		const timed = df.fieldtype === "Datetime";
		if (condition === "Timespan") return period_label(value);
		if (condition === "Between") return range_text(...list_of(value), timed);
		return day_text(value, timed, [">=", "<"].includes(condition));
	}
	if (condition === "Between") {
		const [from, to] = list_of(value);
		return `${number_text(df, from)} – ${number_text(df, to)}`;
	}
	return number_text(df, value);
}

/**
 * What a chip says about a field's filters: its sentence ({0} the field, {1} the value) and the
 * value.
 * @param {Object} df The field.
 * @param {Array[]} rules Its filters, as [condition, value].
 * @returns {{template: string, value: string, more?: string, full?: string}}
 */
function describe(df, rules) {
	if (!rules.length) return { template: "", value: "" };
	if (rules.length > 1) {
		return { template: __("{0} has {1}"), value: __("{0} conditions", [rules.length]) };
	}
	const [condition, value] = rules[0];
	if (condition === "is") {
		return {
			template: __("{0} is {1}"),
			value: value === "set" ? __("set") : __("not set"),
		};
	}
	const hook = frappe.boot.additional_filters_config?.[condition];
	if (hook) {
		const words = __("{0} in {2} {1}", null, "Filter chip: field, period name, period");
		return { template: fill(words, ["{0}", "{1}", __(hook.label)]), value };
	}
	const kind = kind_of(df);
	// a day can be left out only in Advanced: "not on 27 Sep, 00:00"
	if (kind === "date" && condition === "!=") {
		return { template: __("{0} not on {1}"), value: value_text(df, "=", value) };
	}
	// a number range open at one end reads as that end: "at least 500"
	if (kind === "number" && condition === "Between") {
		const [from, to] = list_of(value).concat(["", ""]);
		if (is_blank(to) && !is_blank(from)) return describe(df, [[">=", from]]);
		if (is_blank(from) && !is_blank(to)) return describe(df, [["<=", to]]);
	}
	// a pattern reads as "contains" only when it is one ("%Echo%"); "Echo%", or a % or _ inside
	// (wildcards to the server), reads as it is
	if (["like", "not like"].includes(condition) && df.match !== "like") {
		const contains = /^%[^%_]*%$/.test(String(value));
		const words = contains
			? { like: __("{0} contains {1}"), "not like": __("{0} doesn't contain {1}") }
			: { like: __("{0} like {1}"), "not like": __("{0} not like {1}") };
		return {
			template: words[condition],
			value: `“${contains ? strip_like(value) : value}”`,
		};
	}
	const word = WORDS[kind][condition];
	if (word === undefined) {
		return {
			template: fill(NAMED(), ["{0}", "{1}", condition_name(condition)]),
			value: list_of(value).join(", "),
		};
	}
	const template = word ? word() : PLAIN();
	const full = value_text(df, condition, value);
	// a list names its first value and counts the rest, so the chip stays short: "To Bill +2"
	const labels = kind === "values" ? list_of(value).map((v) => value_label(df, v)) : [];
	if (labels.length > 2 || (labels.length === 2 && condition !== "not in")) {
		return { template, value: labels[0], more: `+${labels.length - 1}`, full };
	}
	return { template, value: full };
}

function ease_width(el, from) {
	const to = el.offsetWidth;
	if (Math.abs(from - to) < 1 || still()) return;
	el.animate(
		[
			{ width: `${from}px`, overflow: "hidden" },
			{ width: `${to}px`, overflow: "hidden" },
		],
		SETTLE
	);
}

function close_gap(gap) {
	if (still() || !gap.isConnected) return gap.remove();
	const space = getComputedStyle(gap.parentElement).columnGap;
	gap.animate(
		[
			{ width: `${gap.offsetWidth}px`, marginInlineEnd: "0px" },
			{ width: "0px", marginInlineEnd: `-${space}` },
		],
		SETTLE
	).finished.then(
		() => gap.remove(),
		() => gap.remove()
	);
}

const key_of = (doctype, fieldname) => `${doctype}\u0000${fieldname}`;
const on_field = (f, doctype, fieldname) => f[0] === doctype && f[1] === fieldname;

// the filter rows hand values back as text ("0" for 0)
const same_rules = (a, b) => {
	const text = (rules) =>
		JSON.stringify(rules.map(([c, v]) => [c, Array.isArray(v) ? v.map(String) : String(v)]));
	return text(a) === text(b);
};

/**
 * A chip as the toolbar box it stands in for, so list scripts written for the boxes keep
 * working: `listview.page.fields_dict.party_type.get_query = …`, `get_value()`, `set_value()`.
 */
class ChipBox {
	constructor(chips, df) {
		this.chips = chips;
		this.df = df;
		this.is_filter_chip = true;
	}

	get $wrapper() {
		return this.chips.chip_of(this.df.doctype, this.df.fieldname)?.$wrapper || $();
	}

	get wrapper() {
		return this.$wrapper[0];
	}

	get_value() {
		const [rule] = this.chips.rules_for(this.df);
		if (!rule || !["=", "like", "descendants of (inclusive)"].includes(rule[0])) return "";
		return rule[0] === "like" ? strip_like(rule[1]) : rule[1];
	}

	get_input_value() {
		return this.get_value();
	}

	set_value(value) {
		const df = this.chips.resolved(this.df);
		let condition = "=";
		if (is_tree(df)) condition = "descendants of (inclusive)";
		else if (df.match === "like" || kind_of(df) === "text") condition = "like";
		const filter_value = condition === "like" ? `%${strip_like(value)}%` : value;
		// an unticked checkbox box filtered nothing
		const empty = is_blank(value) || (df.fieldtype === "Check" && !cint(value));
		const rules = empty ? [] : [[condition, filter_value]];
		this.chips.set_rules(this.df.doctype, this.df.fieldname, rules);
		return Promise.resolve();
	}

	set_input(value) {
		return this.set_value(value);
	}

	// a script that changed `df.options` (a Select's choices) redraws the chip with them
	set_options() {
		this.chips.render();
	}

	toggle(show) {
		this.$wrapper.prop("hidden", !show);
	}

	refresh() {}
}

/**
 * A bar of filter chips: the quick filters stay on it, empty or not; a filter on any other field
 * gets a chip after them, which goes once that filter is removed. Clicking a chip opens the
 * picker for its field type; × removes its filters. The bar holds the filter list: the host
 * passes changes made elsewhere through `set_filters()` and hears the bar's through `onchange`.
 * @example
 * const chips = new frappe.ui.FilterChips({
 *     doctype: "ToDo",
 *     fields: [{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: "Open\nClosed" }],
 *     onchange: (filters) => list.set_filters(filters),
 * });
 * chips.$wrapper.appendTo(toolbar);
 */
frappe.ui.FilterChips = class FilterChips {
	/** @param {FilterChipsOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.doctype = opts.doctype;
		this.fields = (opts.fields || []).map((df) => ({
			typed: kind_of(df) === "text" && df.fieldtype !== "Dynamic Link",
			...df,
			doctype: df.doctype || opts.doctype,
		}));
		this.filters = (opts.filters || []).map((f) => f.slice(0, 4));
		this.chips = new Map();
		this.extra_keys = [];
		this.open_key = null;
		this.listeners = [];
		this.boxes = new Map();
		this.last_picked = new Map();
		this.$wrapper = $('<div class="es-filter-chips" role="group"></div>').attr(
			"aria-label",
			__("Filters")
		);
		this.$wrapper.data("es-filter-chips", this);
		this.cue = scroll_cue(this.$wrapper[0]);
		new ResizeObserver(this.cue).observe(this.$wrapper[0]);
		this.render();
	}

	/** Show the filters as they are now, after they changed somewhere else. */
	set_filters(filters) {
		const next = (filters || []).map((f) => f.slice(0, 4));
		// the rows hand back what the chips just set: nothing to redraw
		const text = (list) => JSON.stringify(list.map((f) => [...f.slice(0, 3), String(f[3])]));
		if (text(next) === text(this.filters)) return;
		this.filters = next;
		// filters replaced from outside the bar (a layout, Advanced filters, a link) close up at
		// once: only what is clicked in the bar keeps its place under the pointer
		const holding = this.holding;
		this.holding = false;
		this.render();
		this.holding = holding;
	}

	get_filters() {
		return this.filters.map((f) => f.slice());
	}

	rules_of(doctype, fieldname) {
		return this.filters
			.filter((f) => on_field(f, doctype, fieldname))
			.map((f) => [f[2], f[3]]);
	}

	/** A field's filters as its picker shows them: a number range is one rule, not two. */
	rules_for(df) {
		const stored = this.rules_of(df.doctype, df.fieldname);
		// the words the person picked ("after 5 Nov", not "on or after 6 Nov"), while the
		// filter is still the one they made
		const picked = this.last_picked.get(key_of(df.doctype, df.fieldname));
		if (picked && same_rules(to_rules(df, picked), stored)) return picked;
		return from_rules(df, stored);
	}

	/** A field's chip, for a host that shows it somewhere else; it stays where it is put. */
	chip_of(doctype, fieldname) {
		return this.chips.get(key_of(doctype, fieldname));
	}

	/** Replace one field's filters (`rules`: [condition, value] pairs) and tell the host. */
	set_rules(doctype, fieldname, rules) {
		const mine = (f) => on_field(f, doctype, fieldname);
		const at = this.filters.findIndex(mine);
		const rest = this.filters.filter((f) => !mine(f));
		const added = rules.map(([condition, value]) => [doctype, fieldname, condition, value]);
		// a field keeps its place among the filters as its values change
		rest.splice(at === -1 ? rest.length : at, 0, ...added);
		this.filters = rest;
		this.render();
		this.opts.onchange?.(this.get_filters());
	}

	/** A quick filter as the toolbar box it replaces, for scripts written for the boxes. */
	box_of(doctype, fieldname) {
		const key = key_of(doctype, fieldname);
		if (!this.boxes.has(key)) {
			const df = this.field_of(doctype, fieldname);
			if (!df) return null;
			this.boxes.set(key, new ChipBox(this, df));
		}
		return this.boxes.get(key);
	}

	/** A Dynamic Link picks from the DocType its sibling's filter names. */
	resolved(df) {
		if (df.fieldtype !== "Dynamic Link") return df;
		const [rule] = this.rules_of(df.doctype, df.options);
		if (rule?.[0] === "=" && rule[1]) return { ...df, fieldtype: "Link", options: rule[1] };
		return { ...df, fieldtype: "Data" };
	}

	field_of(doctype, fieldname) {
		const quick = this.fields.find((df) => same_field(df, { doctype, fieldname }));
		if (quick) return quick;
		const df = this.opts.get_field
			? this.opts.get_field(doctype, fieldname)
			: frappe.meta.get_docfield(doctype, fieldname) || std_field(doctype, fieldname);
		if (!df) return null;
		const label = __(df.label, null, doctype);
		if (doctype === this.doctype) return { ...df, doctype, label };
		return { ...df, doctype, label: `${label} (${this.table_label(doctype)})` };
	}

	/** Where a field's chosen condition is kept: its name, or table and name for a table's field. */
	condition_key(doctype, fieldname) {
		return doctype === this.doctype ? fieldname : `${doctype}.${fieldname}`;
	}

	/** A child table by its label on the form ("Items"); by its DocType when two tables share it. */
	table_label(child) {
		const tables = frappe.meta
			.get_table_fields(this.doctype)
			.filter((df) => df.options === child);
		return tables.length === 1 && tables[0].label ? __(tables[0].label) : __(child);
	}

	/**
	 * A picker closed by a press on another chip redraws the chips once that press is over:
	 * a chip moved from under the pointer would lose the click.
	 */
	hold_for_press() {
		if (this.held) return;
		this.held = true;
		const release = () => {
			if (!this.held) return;
			this.held = false;
			document.removeEventListener("click", release, true);
			this.render();
		};
		document.addEventListener("click", release, true);
		setTimeout(release, 500);
	}

	render() {
		if (this.held) return;
		const quick = this.fields.map((df) => key_of(df.doctype, df.fieldname));
		// other filtered fields, in the order they were added; an open picker keeps its chip
		const filtered = this.filters.map((f) => key_of(f[0], f[1]));
		this.extra_keys = [
			...this.extra_keys.filter((k) => filtered.includes(k) || k === this.open_key),
			...filtered.filter((k) => !quick.includes(k)),
		].filter((k, i, all) => !quick.includes(k) && all.indexOf(k) === i);

		const wanted = [...quick, ...this.extra_keys];
		// a chip that goes while it has focus hands it to the chip that takes its place
		let refocus = null;
		for (const [key, chip] of this.chips) {
			if (!wanted.includes(key)) {
				if (chip.$wrapper[0].contains(document.activeElement)) {
					refocus = [...this.chips.keys()].indexOf(key);
				}
				this.leave_gap(chip);
				chip.destroy();
				this.chips.delete(key);
			}
		}
		const bar = this.$wrapper[0];
		let position = 0;
		for (const key of wanted) {
			const [doctype, fieldname] = key.split("\u0000");
			let chip = this.chips.get(key);
			if (!chip) {
				const df = this.field_of(doctype, fieldname);
				if (!df) continue;
				chip = this.make_chip(df);
				this.chips.set(key, chip);
			}
			const df = this.resolved(chip.df);
			const rules = this.rules_for(chip.df);
			// a typed box holds one "contains" or "is" text; any other filter turns it read-only,
			// and a click opens the picker
			const locked = Boolean(df.typed && rules.length && !box_holds(rules));
			const words = describe(df, rules);
			// a chip being cleared is never held; a page load or applied filter changes a chip at once
			const box = chip.$wrapper[0];
			const clearing = Boolean(
				!chip.$input && box.isConnected && chip.value && !rules.length
			);
			const from = clearing ? box.offsetWidth : 0;
			if (clearing) box.style.minWidth = "";
			else if (this.holding) chip.hold_width();
			chip.set({ more: "", full: "", ...words, locked });
			if (clearing) ease_width(box, from);
			if (df.fieldtype === "Link" && df.options === "User") {
				name_people(
					rules.flatMap(([, value]) => list_of(value).map(strip_like)),
					() => this.render()
				);
			}
			// a chip only moves when it is out of place: moving a focused one drops its focus
			const el = chip.$wrapper[0];
			if (el.parentElement && el.parentElement !== bar) continue;
			// a gap left by a chip that went stays where it is, between its neighbours
			const placed = [...bar.children].filter((c) => !c.matches(".es-filter-chips__gap"));
			if (placed[position] !== el) bar.insertBefore(el, placed[position] || null);
			position++;
		}
		if (refocus !== null) {
			const left = [...this.chips.values()];
			left[Math.min(refocus, left.length - 1)]?.focus();
		}
		this.cue();
		this.listeners.forEach((fn) => fn());
	}

	/** Call `fn` after every redraw, such as a picker elsewhere changing a filter. */
	on_render(fn) {
		this.listeners.push(fn);
	}

	off_render(fn) {
		this.listeners = this.listeners.filter((listener) => listener !== fn);
	}

	make_chip(df) {
		const { doctype, fieldname } = df;
		const key = key_of(doctype, fieldname);
		const label = __(df.label, null, df.doctype);
		let chip;
		const popup = {
			content: () =>
				(this.picker = this.picker_for(df, {
					on_advanced: () => {
						chip.close();
						this.opts.on_advanced?.(doctype, fieldname);
					},
				})),
			popover_class: `es-filter-picker-panel es-filter-picker-panel--${kind_of(df)}`,
			onopen: () => {
				this.open_key = key;
				this.opts.onopen?.(df);
			},
			onclose: (chip, reason) => {
				if (reason === "outside") this.hold_for_press();
				this.picker?.destroy?.();
				this.picker = null;
				this.open_key = null;
				this.render();
			},
		};
		if (df.typed) {
			chip = new frappe.ui.FilterChip({
				label,
				icon: icon_of(df),
				...popup,
				input: {
					onchange: (text) => {
						const exact =
							this.opts.conditions?.[this.condition_key(doctype, fieldname)] === "=";
						const rule = exact ? ["=", text] : ["like", `%${text}%`];
						this.set_rules(doctype, fieldname, text ? to_rules(df, [rule]) : []);
					},
				},
			});
			chip.set = ({ template, value, locked } = {}) => {
				// the box shows the text typed, not the chip's sentence, unless it can't be typed
				const [rule] = this.rules_of(doctype, fieldname);
				const typed = !rule
					? ""
					: rule[0].includes("like")
					? strip_like(rule[1])
					: rule[1];
				// a read-only box reads the sentence after its name: "doesn't contain “Golf”"
				const words = fill(template || PLAIN(), ["", value]).trim();
				frappe.ui.FilterChip.prototype.set.call(chip, {
					value: locked ? words.replace(/^:\s*/, "") : typed,
					locked,
				});
			};
		} else {
			chip = new frappe.ui.FilterChip({
				label,
				icon: icon_of(df),
				...popup,
				onremove: () => this.set_rules(doctype, fieldname, []),
			});
		}
		chip.df = df;
		return chip;
	}

	/** Whether a field's filters fit its picker; if not, they are edited in the host's rows. */
	fits(doctype, fieldname) {
		const field = this.field_of(doctype, fieldname);
		if (!field) return false;
		const df = this.resolved(field);
		const rules = this.rules_for(df);
		if (df.fieldtype === "Datetime" && !rules.every(whole_days)) return false;
		// the pickers write "contains" as "%text%"; "Echo%" would be rewritten on the first edit
		const pattern = ([c, v]) => !c.includes("like") || df.match === "like" || is_contains(v);
		return (
			rules.length <= 1 &&
			rules.every(([c]) => picker_conditions(df).includes(c)) &&
			rules.every(pattern)
		);
	}

	/** Each of a field's filters in words, one per condition: "Checked At after 5 Nov, 10:00". */
	words_of(df, rules) {
		return rules.map((rule) => {
			const { template, value, full = value } = describe(df, [rule]);
			return fill(template, [__(df.label, null, df.doctype), full]);
		});
	}

	/**
	 * The picker for a field, wherever it is shown: under its chip or in a filter panel. A filter
	 * it can't show gets a note whose button calls `on_advanced`. `hint` is a gray line under
	 * the date and text pickers' box. `autofocus` false leaves focus where it is; `clear` false
	 * drops a value list's own Clear, for a host that shows one.
	 */
	picker_for(given, { on_advanced, hint = "", autofocus = true, clear = true } = {}) {
		const { doctype, fieldname } = given;
		// the bar's own field wins, so a panel picks as the chip does (the ID box is typed)
		const field = this.field_of(doctype, fieldname) || given;
		const df = this.resolved(field);
		const rules = this.rules_for(df);
		const peer = field.fieldtype === "Dynamic Link" && df.fieldtype === "Data";
		const peer_label = peer && (this.field_of(doctype, df.options)?.label || df.options);
		// a list needs one type; two picked can't share a list
		const peer_hint = !peer
			? hint
			: this.rules_of(doctype, df.options).length
			? __("Pick one {0} to pick from a list", [peer_label])
			: __("Filter {0} first to pick from a list", [peer_label]);
		const ctx = {
			df,
			doctype: this.doctype,
			rules,
			set: (next) => {
				this.last_picked.set(key_of(doctype, fieldname), next);
				this.set_rules(doctype, fieldname, to_rules(df, next));
			},
			get_query: this.boxes.get(key_of(doctype, fieldname))?.get_query || df.get_query,
			// the other filters, for counts that follow them
			others: this.filters.filter((f) => !on_field(f, doctype, fieldname)),
			condition: this.opts.conditions?.[this.condition_key(doctype, fieldname)],
			remember: (condition) =>
				this.opts.on_condition?.(this.condition_key(doctype, fieldname), condition),
			hint: peer_hint,
			autofocus,
			clear,
		};
		if (this.fits(doctype, fieldname)) return pickers[kind_of(df)](ctx);
		return advanced_notice(ctx, this.words_of(df, rules), on_advanced);
	}

	/**
	 * While on, nothing in the bar moves under the pointer: a chip that gets shorter keeps its
	 * width, and one that goes leaves a gap of its size. Off lets every chip settle.
	 */
	hold_widths(on) {
		this.holding = on;
		if (on) return;
		for (const chip of this.chips.values()) chip.release_width();
		this.$wrapper.children(".es-filter-chips__gap").each((i, gap) => close_gap(gap));
	}

	// a removed chip fades where it was; its room stays while the bar is held
	leave_gap(chip) {
		const el = chip.$wrapper[0];
		if (!el.isConnected || !el.offsetWidth) return;
		if (still() && !this.holding) return;
		const ghost = el.cloneNode(true);
		ghost.inert = true;
		const gap = $('<span class="es-filter-chips__gap" aria-hidden="true"></span>')
			.css("width", el.offsetWidth)
			.append(ghost)
			.insertBefore(el)[0];
		if (still()) return ghost.remove();
		ghost.animate([{ opacity: 1 }, { opacity: 0 }], { ...SETTLE, fill: "forwards" });
		if (!this.holding) close_gap(gap);
	}

	/** Close the chip whose picker is open, if any. */
	close() {
		this.chips.get(this.open_key)?.close();
	}

	destroy() {
		this.picker?.destroy?.();
		for (const chip of this.chips.values()) chip.destroy();
		this.chips.clear();
		this.$wrapper.remove();
	}
};

/**
 * Convenience form: build FilterChips and return the bar. The instance (for `set_filters()`,
 * `get_filters()`) is on `.data("es-filter-chips")`.
 * @param {FilterChipsOpts} opts
 * @returns {JQuery}
 */
frappe.ui.filter_chips = function (opts = {}) {
	return new frappe.ui.FilterChips(opts).$wrapper;
};

export default frappe.ui.FilterChips;
