import {
	can_be_empty,
	duration_text as time_text,
	GROUP_BY_KEYS,
	hook_conditions,
	is_blank,
	is_tree,
	list_of,
	rating_of,
	scale_of,
	stars_of,
	strip_like,
	value_label,
} from "./filter_utils.js";

// The pickers FilterChips opens, one per kind of field. Each takes a context:
//   df     the field
//   doctype  the DocType being filtered (Link searches run for it)
//   rules  the field's filters now, as [condition, value]
//   set(rules)  replace them; [] removes the filter
// and returns the element shown in the chip's Popover; an element with a `destroy()` is told
// when the picker closes.

const icon = (name) => frappe.utils.icon(name, "sm", "", "", "", true);
// a phone (or a tablet, or a phone on its side) would bring up its keyboard over the picker
const has_soft_keyboard = () =>
	window.matchMedia("(max-width: 767.98px), (pointer: coarse)").matches;

// a picker's first field takes focus right after the Popover has placed its own (before any key
// typed meanwhile is read), unless its host keeps focus (`ctx.autofocus` false); phones keep the
// keyboard down
export function focus_soon(el, ctx) {
	if (!el || ctx?.autofocus === false || has_soft_keyboard()) return;
	// a box that holds a value gets the cursor after it, as a text box does
	const take = () => {
		if (!el.isConnected) return false;
		el.focus({ preventScroll: true });
		const end = el.value?.length;
		if (end) {
			try {
				el.setSelectionRange(end, end);
			} catch {
				// a number box has no cursor position to set
			}
		}
		return true;
	};
	queueMicrotask(() => {
		// a picker put on the page later than its Popover opened
		if (!take()) setTimeout(take, 30);
	});
}

const rows_of = (list, rows_selector) =>
	[...list.querySelectorAll(rows_selector)].filter((el) => !el.disabled && el.offsetParent);

/**
 * Up and Down move focus between a list's rows, Home and End to its ends. Down in `entry` (a box
 * above) steps into the list, and Up on the first row steps back to it. As in a Menu, a row is
 * lit only by the keys or the pointer: focus put there on open lights nothing until a key is
 * pressed, and a row hovered takes focus once the keys are in the list.
 */
function arrow_keys(list, rows_selector, entry = null) {
	const rows = () => rows_of(list, rows_selector);
	const focused_row = () =>
		list.contains(document.activeElement) && document.activeElement.matches(rows_selector)
			? document.activeElement
			: null;
	const light = (row) => {
		for (const el of list.querySelectorAll(rows_selector)) {
			el.toggleAttribute("data-highlighted", el === row);
		}
	};
	const lit = () => list.querySelector(`${rows_selector}[data-highlighted]`);
	list.addEventListener("focusin", (e) => {
		if (e.target.matches(rows_selector) && e.target.matches(":focus-visible, :hover")) {
			light(e.target);
		}
	});
	list.addEventListener("focusout", (e) => {
		if (!list.contains(e.relatedTarget)) light(list.querySelector(`${rows_selector}:hover`));
	});
	list.addEventListener("pointermove", (e) => {
		const row = e.target.closest(rows_selector);
		if (e.pointerType === "touch" || !row || row.disabled || row === lit()) return;
		if (focused_row()) row.focus({ preventScroll: true });
		light(row);
	});
	list.addEventListener("pointerleave", () => {
		const row = focused_row();
		light(row?.matches(":focus-visible") ? row : null);
	});
	list.addEventListener("keydown", (e) => {
		const all = rows();
		const at = all.indexOf(document.activeElement);
		// a key the search box inside the list already used (Down into the list) is done
		if (at < 0 || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
		const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: all.length - 1 }[e.key];
		if (to == null) return;
		e.preventDefault();
		if (to < 0) entry?.focus();
		else all[Math.min(to, all.length - 1)].focus();
	});
	// Down from the box goes on from a row the pointer lit, else to the first
	entry?.addEventListener("keydown", (e) => {
		if (e.key !== "ArrowDown" || e.altKey) return;
		const all = rows();
		if (!all.length) return;
		e.preventDefault();
		const at = all.indexOf(lit());
		all[at < 0 ? 0 : Math.min(at + 1, all.length - 1)].focus();
	});
}

/**
 * A list under a search box, keyed as a Combobox is: focus stays in `input`, and at most one row
 * is lit, by the pointer or by Up and Down. Up on the first row goes back to the box; Enter
 * clicks the lit row.
 *
 * Returns `lit()`, the lit row if any; `first(n)`, to light the nth row as n Downs would;
 * `reset()`, to put the light out once the rows answer a new search; and `settle()`, for after
 * a redraw.
 */
export function search_keys(list, rows_selector, input) {
	let lit = null;
	// the row the keys lit, which the light goes back to as the pointer leaves
	let keyed = null;
	let pointer_lit = false;
	const rows = () => rows_of(list, rows_selector);
	const shown = (el) => el?.isConnected && el.offsetParent && list.contains(el);
	const light = (row, scroll = false) => {
		pointer_lit = false;
		if (row === lit) return;
		lit?.removeAttribute("data-highlighted");
		lit = row || null;
		if (!lit) return input.removeAttribute("aria-activedescendant");
		frappe.dom.set_unique_id(lit);
		lit.setAttribute("data-highlighted", "");
		input.setAttribute("aria-activedescendant", lit.id);
		if (scroll) lit.scrollIntoView({ block: "nearest" });
	};
	const key_light = (row) => {
		light(row, true);
		keyed = lit;
	};
	const reset = () => {
		keyed = null;
		light(null);
	};
	const settle = () => {
		if (!shown(keyed)) keyed = null;
		if (!shown(lit)) light(null);
	};

	// a click on a row leaves focus in the box
	list.addEventListener("pointerdown", (e) => {
		if (e.target.closest(rows_selector)) e.preventDefault();
	});
	list.addEventListener("pointermove", (e) => {
		const row = e.target.closest(rows_selector);
		if (e.pointerType === "touch" || !row || row.disabled) return;
		light(row);
		pointer_lit = true;
	});
	list.addEventListener("pointerleave", () => light(shown(keyed) ? keyed : null));
	input.addEventListener("blur", () => {
		if (!pointer_lit) reset();
	});
	input.addEventListener("keydown", (e) => {
		if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
		if (e.isComposing || e.keyCode === 229) return;
		const all = rows();
		const at = all.indexOf(lit);
		let to;
		if (e.key === "ArrowDown") to = Math.min(at + 1, all.length - 1);
		else if (e.key === "ArrowUp" && at >= 0) to = at - 1;
		// with text typed, Home and End move the caret
		else if (e.key === "Home" && !input.value) to = 0;
		else if (e.key === "End" && !input.value) to = all.length - 1;
		else if (e.key === "Enter" && shown(lit)) {
			e.preventDefault();
			lit.click();
			return;
		}
		if (to == null || !all.length) return;
		e.preventDefault();
		if (to < 0) reset();
		else key_light(all[to]);
	});
	return {
		lit: () => (shown(lit) ? lit : null),
		first: (n = 1) => {
			const all = rows();
			if (all.length) key_light(all[Math.min(n, all.length) - 1]);
		},
		reset,
		settle,
	};
}

/**
 * Overlay scrollbars give no hint that more rows follow: while they do, the list's edge fades, as
 * the Combobox's does. Returns the update, for after the rows change.
 */
export function scroll_cue(list) {
	const update = () => {
		const below = list.scrollHeight - list.scrollTop - list.clientHeight > 2;
		list.toggleAttribute("data-more-below", below);
		list.toggleAttribute("data-more-above", list.scrollTop > 2);
		// a row that scrolls sideways (the chips on a short screen); RTL counts down from 0
		const before = Math.abs(list.scrollLeft);
		list.toggleAttribute("data-more-start", before > 2);
		list.toggleAttribute("data-more-end", list.scrollWidth - list.clientWidth - before > 2);
	};
	list.addEventListener("scroll", update, { passive: true });
	return () => requestAnimationFrame(update);
}

const FIELDTYPE_ICONS = {
	Select: "circle-dot",
	Link: "link-2",
	"Dynamic Link": "link",
	Autocomplete: "text-search",
	Date: "calendar",
	Datetime: "calendar-clock",
	Currency: "banknote",
	Float: "hash",
	Int: "hash",
	Percent: "percent",
	Duration: "timer",
	Check: "square-check",
	Data: "type",
	"Small Text": "text-align-start",
	"Text Editor": "file-text",
	Phone: "phone",
};

// the DocField's own icon, else one for its type
export const icon_of = (df) => df.icon || FIELDTYPE_ICONS[df.fieldtype] || "type";

/**
 * A condition and what it takes, read as one box: the condition's menu on the left, the inputs
 * beside it. Returns the box; `$box.condition` is the one picked.
 */
function condition_box({ label, options, value }, on_pick) {
	const $box = $('<div class="es-filter-picker__condition" role="group"></div>').attr(
		"aria-label",
		label
	);
	const text = (v) => options.find((o) => o.value === v)?.label || "";
	const $trigger = frappe.ui.dropdown({
		button: { label: text(value), icon_right: "chevron-down", variant: "ghost" },
		options: () => {
			const item = (o) => ({
				label: o.label,
				selected: o.value === $box.condition,
				onclick: () => {
					if (o.value === $box.condition) return;
					$current.text(o.label);
					$trigger.attr("aria-label", __("Condition: {0}", [o.label]));
					$box.condition = o.value;
					on_pick(o.value);
				},
			});
			// "Is set" and "Is not set" sit apart, below a line: they take no value
			const empty = options.filter((o) => is_set_condition(o.value));
			const rest = options.filter((o) => !is_set_condition(o.value)).map(item);
			if (!empty.length || !rest.length) return options.map(item);
			return [
				...rest,
				{ group: __("Empty or not"), hide_label: true, options: empty.map(item) },
			];
		},
	});
	// every condition's words share one cell, so the button keeps the longest one's width and
	// the box beside it doesn't move when the condition changes
	let $label = $trigger.find(".es-button__label");
	if (!$label.length) $label = $('<span class="es-button__label"></span>').prependTo($trigger);
	const $current = $("<span></span>").text(text(value));
	const sizers = options.map((o) =>
		$('<span class="es-filter-picker__sizer invisible" aria-hidden="true"></span>').text(
			o.label
		)
	);
	$label
		.empty()
		.addClass("es-filter-picker__condition-label")
		.append($current, ...sizers);
	$trigger.attr("aria-label", __("Condition: {0}", [text(value)]));
	$box.condition = value;
	$box.append($trigger);
	return $box;
}

// an empty field, or any value: every condition menu but the checkbox's ends with these
const set_options = (df) =>
	can_be_empty(df)
		? [
				{ label: __("Is set"), value: "is:set" },
				{ label: __("Is not set"), value: "is:not set" },
		  ]
		: [];

// "at most" and "less than" keep the upper end of a range; the others its lower end
const upper_end = (condition) => ["<", "<="].includes(condition);

/**
 * The value a number kept when its condition changes between one box and a range: "at least 5"
 * becomes "from 5", "Between 5 and 9" becomes "at most 9". Null when there is nothing to carry.
 */
function carried_value(was, now, { value, from, to }) {
	if (is_set_condition(was) || is_set_condition(now)) return null;
	if (now === "Between" && was !== "Between" && !is_blank(value)) {
		return upper_end(was) ? { from: "", to: value } : { from: value, to: "" };
	}
	if (was === "Between" && now !== "Between") {
		const [near, far] = upper_end(now) ? [to, from] : [from, to];
		const kept = is_blank(near) ? far : near;
		if (!is_blank(kept)) return { value: kept };
	}
	return null;
}
const is_set_condition = (condition) => String(condition).startsWith("is:");
const set_rule = (condition) => [["is", condition.slice(3)]];
const condition_of = (rule) => (rule[0] === "is" ? `is:${rule[1]}` : rule[0]);
// From after To means the same span
const in_order = (a, b) => (a != null && b != null && a > b ? [b, a] : [a, b]);

function show_set_hint($box, df, condition) {
	const only = is_set_condition(condition);
	$box.attr("data-only-condition", only ? "" : null);
	let $hint = $box.next(".es-filter-picker__set-hint");
	if (!$hint.length) {
		$hint = $('<p class="es-filter-picker__hint es-filter-picker__set-hint"></p>');
		$hint.insertAfter($box);
	}
	const label = __(df.label, null, df.doctype);
	$hint
		.prop("hidden", !only)
		.text(
			condition === "is:set"
				? __("Shows records where {0} has a value", [label])
				: __("Shows records where {0} is empty", [label])
		);
}

// the camera shows under the box: a scanner dialog would take focus and close the panel
function barcode_scanner(df, on_scan) {
	if (df.fieldtype !== "Barcode") {
		return { $button: $(), $area: $(), stop() {} };
	}
	const $area = $('<div class="es-filter-picker__scanner barcode-scanner" hidden></div>');
	let scanner = null;
	const hide = () => {
		scanner = null;
		$area.prop("hidden", true);
		$button.attr("aria-expanded", "false");
	};
	const stop = () => {
		scanner?.stop_scan();
		hide();
	};
	const start = () => {
		$area.prop("hidden", false);
		$button.attr("aria-expanded", "true");
		scanner = new frappe.ui.Scanner({
			container: $area,
			on_scan: (data) => {
				if (!data?.result?.text) return;
				// the scanner stops itself after a code; stopping it again would fail
				hide();
				on_scan(data.result.text);
			},
		});
		scanner.scan();
	};
	const $button = frappe.ui.button({
		icon: "scan-barcode",
		variant: "ghost",
		size: "xs",
		tooltip: __("Scan"),
		css_class: "es-filter-picker__scan",
		attrs: { "aria-expanded": "false" },
		onclick: () => (scanner ? stop() : start()),
	});
	return { $button, $area, stop };
}

function input_el({ placeholder, value = "", label, type = "text" }) {
	return $(`<input class="es-filter-picker__input" autocomplete="off">`)
		.attr({ type, placeholder, "aria-label": label || placeholder })
		.val(value);
}

// a range's two boxes, each followed by its name: shown once the box is filled where the
// boxes stack and their placeholders are gone (a phone)
function range_boxes($from, $to) {
	const name = (text) =>
		$('<span class="es-filter-picker__box-label" aria-hidden="true"></span>').text(text);
	return [$from, name(__("From")), $to, name(__("To"))];
}

const PAGE = 20;

// Select options as rows: text options, or { value, label } ones (Document Status)
function listed_options(df) {
	if (!["Select", "Autocomplete"].includes(df.fieldtype)) return null;
	const options = Array.isArray(df.options) ? df.options : String(df.options || "").split("\n");
	return options
		.filter((o) => o !== "" && o != null)
		.map((o) => (typeof o === "object" ? o : { value: o, label: __(o, null, df.doctype) }));
}

// "eval:" filters read a form's values, which a list doesn't have
function link_filters_of(df) {
	if (!df.link_filters) return {};
	try {
		return Object.fromEntries(
			JSON.parse(df.link_filters)
				.filter(([, , , value]) => !String(value).startsWith("eval:"))
				.map(([, fieldname, condition, value]) => [fieldname, [condition, value]])
		);
	} catch {
		return {};
	}
}

// a Link field's get_query in any of its forms (filters, { filters, query }, a method, a function
// of the form, which a list doesn't have) as search_link's arguments
function query_args(get_query) {
	const q = typeof get_query === "function" ? get_query() : get_query;
	if (typeof q === "string") return { query: q };
	if (!$.isPlainObject(q)) return {};
	if (q.query || q.filters) return q;
	return { filters: q };
}

function search_filters(df, filters, people) {
	const own = link_filters_of(df);
	// a form may take end groups only; a tree filter picks a group for everything under it
	if (is_tree(df)) delete own.is_group;
	if (Array.isArray(filters)) {
		return [...filters, ...Object.entries(own).map(([field, rule]) => [field, ...rule])];
	}
	const all = { ...filters, ...own, ...(people ? { ignore_user_type: 1 } : {}) };
	return Object.keys(all).length ? all : undefined;
}

const NOT_SET = "\u0000not set";
// the user search leaves out the built-in users, yet records are made by them too
const STANDARD_USERS = ["Administrator", "Guest"];

// a user search row's name: its title, or its search fields without the ID, as a site that
// doesn't show titles in links sends it
function person_name({ value, label, description }) {
	if (label && label !== value) return strip_html(label);
	const rest = strip_html(description || "")
		.split(", ")
		.filter((part) => part && part !== value);
	return rest.join(", ") || value;
}
// a picked row glides to its group gently enough for the eye to follow it
const MOTION = { duration: 300, easing: "cubic-bezier(0, 0, 0.2, 1)" };

export function values(ctx) {
	const { df } = ctx;
	const [rule] = ctx.rules;
	const people = df.fieldtype === "Link" && df.options === "User";
	// a record in a tree stands for its branch, so one is picked at a time
	const tree = is_tree(df);
	// Assigned To and Tags hold a list as text: one value at a time, matched with like
	const like = df.match === "like";
	const single = tree || like;
	const listed = listed_options(df);
	const counts = typeof df.counts === "function" ? df.counts() : !!df.counts;

	let positive =
		!rule ||
		["=", "in", "descendants of (inclusive)", "like"].includes(rule[0]) ||
		(rule[0] === "is" && rule[1] !== "set");
	let picked = [];
	if (rule?.[0] === "is") picked = [NOT_SET];
	else if (["in", "not in"].includes(rule?.[0])) picked = list_of(rule[1]);
	else if (rule) picked = [like ? strip_like(rule[1]) : rule[1]];
	let query = "";
	// the search the rows answer, and an Enter or a Down pressed before they did
	let answered = "";
	let enter_waiting = false;
	let down_waiting = 0;
	// closed: a search still on its way changes nothing
	let gone = false;
	let rows = [];
	let start = 0;
	let more = false;
	let loading = false;
	let failed = false;
	let request = 0;
	const known = new Map(); // value -> row, so a pick keeps its label and picture
	const not_set = { value: NOT_SET, label: __("Not set") };
	// values come back from the filter rows as text ("0" for 0), so they compare as text
	const is_picked = (value) => picked.some((p) => String(p) === String(value));

	const $root = $('<div class="es-filter-picker es-filter-picker--values"></div>');
	const $tools = $('<div class="es-filter-picker__tools"></div>').appendTo($root);
	const $list = $('<div class="es-filter-picker__list" role="listbox" tabindex="-1"></div>')
		.attr({
			"aria-label": __(df.label, null, df.doctype),
			"aria-multiselectable": single ? null : "true",
		})
		.appendTo($root);
	frappe.dom.set_unique_id($list);
	const $end = $('<div class="es-filter-picker__end shrink-0 h-px" aria-hidden="true"></div>');
	const cue = scroll_cue($list[0]);
	const $status = $('<span class="sr-only" role="status"></span>');

	// one box, as the other pickers have: the condition's menu, then the search; a tree gets the
	// search alone, as the server has no "not under"
	const $field = $('<label class="es-filter-picker__search"></label>');
	const $search = input_el({
		placeholder: __("Search {0}", [__(df.label, null, df.doctype)]),
	}).attr("aria-controls", $list.attr("id"));
	const $clear = frappe.ui
		.button({ icon: "x", size: "xs", variant: "ghost", tooltip: __("Clear search") })
		.prop("hidden", true)
		.on("click", () => {
			$search.val("").trigger("input");
			// a phone's keyboard stays down; the next tap in the box brings it back
			if (has_soft_keyboard()) $search.trigger("blur");
			else $search.trigger("focus");
		});
	const $spinner = $('<span class="es-spinner" aria-hidden="true" hidden></span>');
	$field.append(icon("search"), $search, $spinner, $clear);
	const search = frappe.utils.debounce(() => {
		start = 0;
		load();
	}, 250);
	$search.on("input", () => {
		query = $search.val().trim();
		$clear.prop("hidden", !query);
		enter_waiting = false;
		down_waiting = 0;
		search();
	});
	// Enter, or Down, before this search has answered waits for its rows, rather than landing on
	// old ones; Enter with no row lit picks the first match
	$search.on("keydown", (e) => {
		if (!["Enter", "ArrowDown"].includes(e.key) || !query) return;
		if (e.originalEvent?.isComposing || e.keyCode === 229) return;
		// a next page on its way keeps the rows shown; only a new search's rows are awaited
		const waiting = answered !== query || (loading && !start);
		if (!waiting && (e.key === "ArrowDown" || keys.lit())) return;
		e.preventDefault();
		if (!waiting) return pick_first();
		if (e.key === "Enter") enter_waiting = true;
		else down_waiting += 1;
		search.flush();
	});
	const keys = search_keys($list[0], ".es-menu__item", $search[0]);
	if (tree) {
		$tools.append($field);
	} else {
		const match = [
			{ label: __("Is"), value: "is" },
			{ label: __("Is not"), value: "not" },
		];
		const $box = condition_box(
			{
				label: __(df.label, null, df.doctype),
				options: match,
				value: positive ? "is" : "not",
			},
			(value) => {
				positive = value === "is";
				if (picked.length) save();
				render();
			}
		);
		$tools.append($box.addClass("flex-1").append($field));
	}

	function option_of(value) {
		if (value === NOT_SET) return not_set;
		if (known.has(String(value))) return known.get(String(value));
		if (people && value === frappe.session.user) return me_option();
		const label = value_label(df, value);
		return { value, label, description: people && label !== value ? value : null };
	}

	function save() {
		if (!picked.length) return ctx.set([]);
		if (picked[0] === NOT_SET) return ctx.set([["is", positive ? "not set" : "set"]]);
		if (tree) return ctx.set([["descendants of (inclusive)", picked[0]]]);
		if (like) return ctx.set([[positive ? "like" : "not like", `%${picked[0]}%`]]);
		if (picked.length === 1) return ctx.set([[positive ? "=" : "!=", picked[0]]]);
		ctx.set([[positive ? "in" : "not in", picked.slice()]]);
	}

	function toggle(value) {
		// a radio stays picked; Clear or the chip's × takes it off
		if (single && is_picked(value)) return;
		if (is_picked(value)) {
			picked = picked.filter((v) => String(v) !== String(value));
		} else if (single || value === NOT_SET || picked[0] === NOT_SET) {
			// a tree has no Is not: a record picked keeps its branch
			if (tree && value !== NOT_SET) positive = true;
			// "Not set" is a filter of its own: it can't join values
			picked = [value];
		} else {
			picked = [...picked, value];
		}
		save();
		render();
	}

	// "Not set" leads the values, and typing the start of its name finds it
	function shows_not_set() {
		return (
			can_be_empty(df) &&
			not_set.label.toLowerCase().startsWith(query.toLowerCase()) &&
			!is_picked(NOT_SET) &&
			!rows.some((r) => r.value === NOT_SET)
		);
	}

	// a list that keeps one value keeps the first match: a second Enter changes nothing
	function pick_first() {
		const shown = shows_not_set() ? [not_set, ...rows] : rows;
		const first = single ? shown[0] : shown.find((r) => !is_picked(r.value));
		if (first && !is_picked(first.value)) toggle(first.value);
	}

	function row_el(option) {
		const selected = is_picked(option.value);
		const $row = $(
			'<button type="button" class="es-menu__item" role="option" tabindex="-1"></button>'
		).attr("aria-selected", selected ? "true" : "false");
		// a list that keeps one value (a tree, Assigned To) marks it with a radio, not a tick box
		const mark = icon(positive ? "check" : "minus");
		$row.append(
			single
				? '<span class="es-combobox__radio" aria-hidden="true"></span>'
				: `<span class="es-combobox__check" aria-hidden="true">${mark}</span>`
		);
		if (people) {
			$row.append(
				option.value === NOT_SET
					? '<span class="es-menu__icon-space"></span>'
					: frappe.ui.avatar.html({
							label:
								option.value === frappe.session.user
									? option.description
									: option.label,
							image: frappe.user_info(option.value)?.image,
							size: "sm",
					  })
			);
		}
		const $label = $('<span class="es-menu__label"></span>').text(option.label);
		if (option.description && option.description !== option.label) {
			$label.append(
				$('<span class="es-menu__description"></span>').text(option.description)
			);
		}
		$row.append($label).on("click", () => toggle(option.value));
		if (option.count != null) {
			$row.append($('<span class="es-filter-picker__count"></span>').text(option.count));
		}
		$row.data("value", option.value);
		return $row;
	}

	function slide(was) {
		if (!was.size || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
		for (const [key, $el] of drawn) {
			const el = $el[0];
			if (!was.has(key)) {
				el.animate(
					[{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1 }],
					MOTION
				);
				continue;
			}
			const dy = was.get(key) - el.getBoundingClientRect().top;
			if (Math.abs(dy) < 1) continue;
			el.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], MOTION);
		}
	}

	function header_el(title, clear) {
		const $header = $('<div class="es-filter-picker__group"></div>');
		$header.append($('<span class="es-menu__group-label"></span>').text(title));
		if (clear) {
			$header.append(
				frappe.ui.button({
					label: __("Clear"),
					size: "sm",
					variant: "ghost",
					onclick: () => {
						picked = [];
						save();
						render();
						// the button is gone: focus stays in the picker, so Escape still closes it
						$search.trigger("focus");
					},
				})
			);
		}
		return $header;
	}

	// rows and headers stay the same elements from one draw to the next, so a ticked row slides
	// to its new place instead of jumping
	const drawn = new Map();
	function render() {
		const top = $list.scrollTop();
		const was = new Map();
		for (const [key, $el] of drawn) {
			if ($el[0].isConnected) was.set(key, $el[0].getBoundingClientRect().top);
		}
		$list.children().detach();
		const shown = new Set();
		const add = (key, make) => {
			if (!drawn.has(key)) drawn.set(key, make());
			shown.add(key);
			return drawn.get(key).appendTo($list);
		};
		// a count, a name or a second line that arrives later (Not set before the counts, a
		// person's name after a search), or Is turned to Is not, gets a fresh row
		const add_row = (option) =>
			add(
				`o:${positive}:${option.value}:${option.count ?? ""}:${option.label}:${
					option.description || ""
				}`,
				() => row_el(option)
			).attr("aria-selected", is_picked(option.value) ? "true" : "false");
		const show_picked = picked.length && !query;
		const rest = show_picked ? rows.filter((r) => !is_picked(r.value)) : rows;
		const unpicked = shows_not_set() ? [not_set, ...rest] : rest;
		if (show_picked) {
			add("h:selected", () => header_el("", ctx.clear !== false))
				.find(".es-menu__group-label")
				.text(
					positive
						? __("Selected · {0}", [picked.length])
						: __("Excluded · {0}", [picked.length])
				);
			picked.forEach((v) => add_row(option_of(v)));
			if (unpicked.length || loading) add("h:all", () => header_el(__("All")));
		}
		unpicked.forEach(add_row);
		for (const key of [...drawn.keys()]) if (!shown.has(key)) drawn.delete(key);
		// loading looks as the Combobox's does: a spinner in the search, placeholder rows while
		// the list is empty, and a row at the end while more pages are left
		$spinner.prop("hidden", !loading || Boolean(start));
		if (loading && !rows.length) {
			$list.append(
				$('<div class="es-menu__group"></div>').append(
					["55%", "70%", "45%"].map(
						(width) =>
							`<div class="flex items-center gap-2 px-2 py-1.5">${frappe.ui.skeleton.html(
								{ css_class: "size-6 rounded-full" }
							)}${frappe.ui.skeleton.html({ width, height: "12px" })}</div>`
					)
				)
			);
		} else if (more && rows.length) {
			$list.append(
				$('<div class="es-menu__loading" aria-hidden="true"></div>').append(
					'<span class="es-spinner"></span>',
					document.createTextNode(__("Loading more..."))
				)
			);
		} else if (failed) {
			$list.append(
				$('<div class="es-menu__empty"></div>').text(
					__("Couldn't load {0}", [__(df.options)])
				)
			);
		} else if (!unpicked.length && query) {
			$list.append(
				$('<div class="es-menu__empty"></div>').text(__("No results for {0}", [query]))
			);
		} else if (!rows.length && !picked.length) {
			$list.append(
				$('<div class="es-menu__empty"></div>').text(
					listed
						? __("No options to pick")
						: counts
						? __("Nothing to pick yet")
						: __("There are no {0} records yet", [__(df.options)])
				)
			);
		}
		$list.append($end, $status);
		$status.text(loading && start ? __("Loading more...") : "");
		$list.scrollTop(top);
		slide(was);
		keys.settle();
		cue();
		// rows gliding into place still make the list look taller; look again once they land
		setTimeout(cue, MOTION.duration);
	}

	// the values these records have, most used first, with how many have each
	let counted;
	async function load_counts() {
		if (!counted) {
			loading = true;
			render();
			counted = await fetch_counts().catch(() => {
				failed = true;
				return [];
			});
			if (gone) return;
			counted.forEach((r) => known.set(String(r.value), r));
			loading = false;
		}
		const q = query.toLowerCase();
		rows = counted.filter((r) => !q || (r.search || r.label).toLowerCase().includes(q));
		render();
		answer(query);
	}

	async function fetch_counts() {
		if (df.fieldname === "_user_tags") {
			const { stats } = await frappe.xcall("frappe.desk.reportview.get_sidebar_stats", {
				stats: ["_user_tags"],
				doctype: ctx.doctype,
				filters: ctx.others,
			});
			return (stats._user_tags || [])
				.map(([tag, count], i, all) =>
					// the server ends the list with the records that have no tags
					i === all.length - 1
						? { ...not_set, count }
						: { value: tag, label: tag, count }
				)
				.filter((r) => r.count);
		}
		const keys = GROUP_BY_KEYS;
		const counts = await frappe.xcall("frappe.desk.listview.get_group_by_count", {
			doctype: ctx.doctype,
			current_filters: ctx.others,
			field: Object.keys(keys).find((key) => keys[key] === df.fieldname) || df.fieldname,
		});
		const me = frappe.session.user;
		return counts
			.filter((c) => c.count)
			.sort((a, b) => (b.name === me) - (a.name === me))
			.map((c) => {
				if (c.name == null) return { ...not_set, count: c.count };
				if (people && c.name === me) return { ...me_option(), count: c.count };
				const label = c.title || (people ? frappe.user.full_name(c.name) : c.name);
				return { value: c.name, label, count: c.count, search: `${label} ${c.name}` };
			});
	}

	function standard_users(found) {
		const q = query.toLowerCase();
		return STANDARD_USERS.filter(
			(user) =>
				user !== frappe.session.user &&
				user.toLowerCase().includes(q) &&
				!found.some((r) => r.value === user)
		).map((user) => {
			const option = { value: user, label: frappe.user.full_name(user), description: user };
			known.set(user, option);
			return option;
		});
	}

	function me_option() {
		const me = frappe.session.user;
		const name = frappe.user_info(me).fullname;
		const label = __("Me");
		return { value: me, label, description: name, search: `${label} ${name} ${me}` };
	}

	function me_first(list, add) {
		const me = frappe.session.user;
		const rest = list.filter((o) => o.value !== me);
		if (!add && rest.length === list.length) return list;
		const mine = me_option();
		known.set(me, mine);
		return [mine, ...rest];
	}

	// rows now answer `asked`: a Down pressed while they were on their way lights the first, and
	// an Enter picks
	function answer(asked) {
		if (gone) return;
		if (asked !== answered) keys.reset();
		answered = asked;
		if (asked !== query) return;
		if (down_waiting) keys.first(down_waiting);
		if (enter_waiting) keys.lit() ? keys.lit().click() : pick_first();
		down_waiting = 0;
		enter_waiting = false;
	}

	async function load() {
		if (counts) return load_counts();
		const asked = query;
		if (listed) {
			const q = query.toLowerCase();
			rows = listed.filter((o) => !q || o.label.toLowerCase().includes(q));
			rows.forEach((r) => known.set(String(r.value), r));
			render();
			return answer(asked);
		}
		const id = ++request;
		loading = true;
		failed = false;
		if (!start) rows = [];
		render();
		// a list script's get_query narrows the records; people filters cover everyone who can
		// own or be assigned a document
		const { query: method, filters, ...extra } = query_args(ctx.get_query);
		let page;
		try {
			page = await frappe.call({
				method: "frappe.desk.search.search_link",
				type: "GET",
				args: {
					...extra,
					doctype: df.options,
					txt: query,
					query: method,
					page_length: PAGE,
					start,
					reference_doctype: ctx.doctype,
					link_fieldname: df.fieldname,
					filters: search_filters(df, filters, people),
				},
				no_spinner: true,
				silent: true,
			});
		} catch {
			// the server shows why (no permission, a bad query); the list stops loading
			failed = id === request;
		}
		// an older search that answers late is dropped
		if (gone || id !== request) return;
		const found = (page?.message || []).map((r) => {
			const option = people
				? { value: r.value, label: person_name(r), description: r.value }
				: {
						value: r.value,
						label: strip_html(r.label || r.value),
						description: strip_html(r.description || ""),
				  };
			known.set(String(option.value), option);
			// the chip reads the same name the row showed, for records the desk hasn't seen
			if (option.label !== option.value) {
				frappe.utils.add_link_title(df.options, option.value, option.label);
			}
			return option;
		});
		more = found.length === PAGE;
		const asks_me = !query || __("Me").toLowerCase().startsWith(query.toLowerCase());
		const add_me = !start && asks_me && !method && !filters;
		const built_in =
			people && !start && query && !method && !filters ? standard_users(found) : [];
		rows = start ? [...rows, ...found] : [...found, ...built_in];
		if (people) rows = me_first(rows, add_me);
		start += found.length;
		loading = false;
		render();
		answer(asked);
	}

	const observer = new IntersectionObserver(
		(entries) => {
			if (entries.some((e) => e.isIntersecting) && more && !loading) load();
		},
		{ root: $list[0], rootMargin: "48px" }
	);
	observer.observe($end[0]);

	load();
	focus_soon($search[0], ctx);
	$root[0].destroy = () => {
		gone = true;
		search.cancel();
		observer.disconnect();
	};
	return $root[0];
}

const DAY_CONDITIONS = ["=", "<", ">", "<=", ">="];

const PERIODS = [
	["today", "yesterday"],
	["this week", "last week", "this month", "last month", "this quarter", "last quarter"],
	["last 7 days", "last 30 days", "last 90 days"],
	["next 7 days", "next 30 days", "next month"],
];

/** A desk timespan ("last month") as its label ("Last Month"), as the Advanced rows name it. */
let period_labels;
export const period_label = (value) => {
	period_labels ??= new Map(
		frappe.ui.filter_utils
			.get_timespan_options(["Last", "Yesterday", "Today", "This", "Next"])
			.map((o) => [o.value, o.label])
	);
	return period_labels.get(value) ?? __(String(value).replace(/\b\w/g, (c) => c.toUpperCase()));
};

// the days a timespan covers, to show on the calendar (the server decides the filter itself)
function period_range(value) {
	const today = moment().startOf("day");
	if (value === "today") return [today, today];
	if (value === "yesterday")
		return [today.clone().subtract(1, "day"), today.clone().subtract(1, "day")];
	if (value === "tomorrow") return [today.clone().add(1, "day"), today.clone().add(1, "day")];
	if (value === "last 6 months" || value === "next 6 months") {
		const [from, to] = value === "last 6 months" ? [-6, -3] : [3, 6];
		return [
			today.clone().add(from, "months").startOf("quarter"),
			today.clone().add(to, "months").endOf("quarter").startOf("day"),
		];
	}
	let m = value.match(/^(last|next) (\d+) days$/);
	if (m) {
		const days = Number(m[2]);
		return m[1] === "last"
			? [today.clone().subtract(days, "days"), today]
			: [today, today.clone().add(days, "days")];
	}
	m = value.match(/^(last|this|next) (week|month|quarter|year)$/);
	if (!m) return null;
	const shift = { last: -1, this: 0, next: 1 }[m[1]];
	if (m[2] === "week") {
		const start = today.clone().startOf("week").add(shift, "weeks");
		return [start, start.clone().add(6, "days")];
	}
	const start = today.clone().add(shift, m[2]).startOf(m[2]);
	return [start, start.clone().endOf(m[2]).startOf("day")];
}

// a typed date: the user's day/month order with any of - / . between, short or long, then ISO and
// "5 Nov 2026"; null when blank, undefined when it can't be read
function read_day(text) {
	const t = text.trim();
	if (!t) return null;
	const user_fmt = frappe.datetime.get_user_date_fmt().toUpperCase();
	const loose = user_fmt.replace("DD", "D").replace("MM", "M");
	const short_year = (f) => f.replace("YYYY", "YY");
	const formats = ["-", "/", "."].flatMap((sep) =>
		[user_fmt, loose, short_year(user_fmt), short_year(loose)].map((f) =>
			f.replace(/[-/.]/g, sep)
		)
	);
	formats.push("YYYY-MM-DD", "D MMM YYYY", "D MMMM YYYY");
	const day = moment(t, formats, true);
	return day.isValid() ? day.format("YYYY-MM-DD") : undefined;
}

export function date(ctx) {
	const { df } = ctx;
	const [rule] = ctx.rules;
	const show = (day) => (day ? frappe.datetime.str_to_user(day, false, true) : "");
	const options = [
		{ label: __("Between"), value: "Between" },
		{ label: __("On"), value: "=" },
		{ label: __("Before"), value: "<" },
		{ label: __("After"), value: ">" },
		{ label: __("On or before"), value: "<=" },
		{ label: __("On or after"), value: ">=" },
		...set_options(df),
	];
	let condition = "Between";
	if (rule?.[0] === "is" || DAY_CONDITIONS.includes(rule?.[0])) condition = condition_of(rule);
	let current = rule ? { condition: rule[0], value: rule[1] } : null;
	// periods an app adds through the filters_config hook (Fiscal Year), fetched once and kept
	// where the Advanced rows keep them
	const configs = frappe.boot.additional_filters_config;
	const choices_of = (field) =>
		(field?.options || []).map((o) =>
			typeof o === "object" ? { ...o, value: String(o.value) } : { value: o, label: o }
		);
	const hooks = hook_conditions(df).map((key) => ({
		key,
		...configs[key],
		choices: choices_of(configs[key].data),
	}));
	const hook_choice = (key, value) =>
		hooks.find((h) => h.key === key)?.choices.find((c) => String(c.value) === String(value));

	const $root = $('<div class="es-filter-picker es-filter-picker--date"></div>');
	const $head = $('<div class="es-filter-picker__head"></div>').appendTo($root);
	const $error = $('<p class="es-filter-picker__error" role="alert" hidden></p>');
	const $hint = $('<p class="es-filter-picker__hint"></p>').text(ctx.hint || "");
	const $body = $('<div class="es-filter-picker__body flex min-h-0"></div>').appendTo($root);
	const $periods = $(
		'<div class="es-filter-picker__periods" role="group" tabindex="-1"></div>'
	).attr("aria-label", __("Periods"));
	const $calendar = $('<div class="es-filter-picker__calendar"></div>');
	$body.append($periods, $calendar);
	const periods_cue = scroll_cue($periods[0]);

	const $from = input_el({ placeholder: __("From"), label: __("From date") });
	arrow_keys($periods[0], ".es-menu__item", $from[0]);
	const $to = input_el({ placeholder: __("To"), label: __("To date") });
	const $box = condition_box(
		{ label: __(df.label, null, df.doctype), options, value: condition },
		(value) => {
			// a day clicked on the calendar, waiting for the second, counts as the filter
			const was = first_day ? { condition: "=", value: first_day } : current;
			const days = first_day
				? [moment(first_day), moment(first_day)]
				: (was && span()) || [];
			condition = value;
			apply(day_rules(was, value, days));
			draw();
		}
	);

	// the days kept when the condition changes: a single day keeps its date, a range or a
	// period keeps the end that still means the same ("1 – 5 Aug", then "on or after": 1 Aug),
	// and a single day becomes the matching side of a range ("before 5 Aug": up to 4 Aug)
	function day_rules(was, now, days) {
		if (is_set_condition(now)) return set_rule(now);
		if (!was) return [];
		const single = DAY_CONDITIONS.includes(was.condition);
		const day = (d, shift = 0) =>
			d ? frappe.datetime.add_days(d.format("YYYY-MM-DD"), shift) : "";
		if (single && DAY_CONDITIONS.includes(now)) return [[now, was.value]];
		if (single && now === "Between") {
			const d = moment(was.value);
			const ends = {
				"=": [day(d), day(d)],
				">=": [day(d), ""],
				">": [day(d, 1), ""],
				"<=": ["", day(d)],
				"<": ["", day(d, -1)],
			}[was.condition];
			return ends ? [["Between", ends]] : [];
		}
		if (!single && DAY_CONDITIONS.includes(now)) {
			const [from, to] = days;
			const kept = {
				"=": day(from || to),
				">=": day(from),
				">": day(from, -1),
				"<=": day(to),
				"<": day(to, 1),
			}[now];
			return kept ? [[now, kept]] : [];
		}
		return [];
	}
	$head.append($box, $error, $hint);

	function apply(rules) {
		first_day = null;
		current = rules.length ? { condition: rules[0][0], value: rules[0][1] } : null;
		$error.prop("hidden", true);
		$from.add($to).removeAttr("aria-invalid");
		ctx.set(rules);
	}

	// the days the filter covers now; a Between open at one end has a null there
	function span() {
		if (!current) return null;
		if (current.condition === "Timespan") return period_range(current.value);
		const choice = hook_choice(current.condition, current.value);
		if (choice?.query_value) return choice.query_value.map((day) => moment(day));
		if (current.condition === "Between") {
			const [from, to] = Array.isArray(current.value)
				? current.value
				: list_of(current.value);
			return [from ? moment(from) : null, to ? moment(to) : null];
		}
		if (current.condition === condition) return [moment(current.value), moment(current.value)];
		return null;
	}

	function fill_inputs() {
		const days = span();
		$from.val(days?.[0] ? show(days[0].format("YYYY-MM-DD")) : "");
		$to.val(days?.[1] ? show(days[1].format("YYYY-MM-DD")) : "");
		before = `${$from.val()}|${$to.val()}`;
	}

	function commit_typed() {
		const from = read_day($from.val());
		const to = condition === "Between" ? read_day($to.val()) : null;
		const bad = [from === undefined && $from.val(), to === undefined && $to.val()].find(
			Boolean
		);
		if (bad) {
			(from === undefined && $from.val() ? $from : $to).attr("aria-invalid", "true");
			$error
				.text(
					__("Can't read {0}. Type a date like {1}.", [
						bad,
						show(frappe.datetime.get_today()),
					])
				)
				.prop("hidden", false);
			return;
		}
		if (condition !== "Between") {
			apply(from ? [[condition, from]] : []);
		} else if (!from && !to) {
			apply([]);
		} else {
			const [a, b] = in_order(from, to);
			apply([["Between", [a || "", b || ""]]]);
		}
		refresh();
	}

	// a box shown as unreadable is read again even when its text is back to what is applied
	const changed = () => `${$from.val()}|${$to.val()}` !== before || !$error.prop("hidden");
	// typing applies on Enter or on leaving the boxes, and only when something was typed, so a
	// period such as "This Month" stays a period when the boxes are left as they were
	let before = "";
	for (const $input of [$from, $to]) {
		$input.on("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				commit_typed();
			}
		});
		// in the phone sheet a whole typed date is the draft at once, so Apply counts it
		$input.on("input", () => {
			if (!$input.closest(".es-bottom-sheet").length) return;
			const boxes = condition === "Between" ? [$from, $to] : [$from];
			const whole = boxes.every(($i) => {
				const day = read_day($i.val());
				return day && show(day) === $i.val();
			});
			if (whole && changed()) commit_typed();
		});
		// moving from one box to the other saves nothing yet; a period clicked next is the filter
		$input.on("blur", (e) => {
			const next = e.relatedTarget;
			if (next === $from[0] || next === $to[0] || pressing === "period") return;
			const save = () => {
				if (!gone && changed()) commit_typed();
			};
			// a calendar day pressed is clicked next: the typed day is saved first, so the click
			// adds to it ("From" typed, "To" clicked)
			if (pressing === "calendar") return save();
			// saved once focus has landed, so the redraw keeps it on the row Tab moved to
			setTimeout(save);
		});
	}
	// a press on a period or a calendar day ends in a click on what is under it then
	let pressing = null;
	const press = (what) => () => {
		pressing = what;
		document.addEventListener("pointerup", () => (pressing = null), { once: true });
	};
	$periods.on("pointerdown", press("period"));
	$calendar.on("pointerdown", press("calendar"));

	// a menu row beside the calendar; a phone's are buttons, the pick the outline button
	function period_row(label, active, rule) {
		let $row;
		if (frappe.is_mobile()) {
			$row = frappe.ui.button({ label, variant: active ? "outline" : undefined });
		} else {
			const $label = $('<span class="es-menu__label"></span>').text(label);
			frappe.ui.tooltip($label, { text: label, only_on_overflow: true });
			$row = $('<button type="button" class="es-menu__item"></button>').append($label);
		}
		return $row
			.attr("aria-pressed", active ? "true" : "false")
			.attr("data-state", active ? "checked" : null)
			.attr("data-key", JSON.stringify(rule))
			.on("click", () => {
				apply(active ? [] : [rule]);
				refresh();
				show_top();
			});
	}

	// a phone shows the boxes and the calendar a pick filled, at the pane's top, not the period
	// the redraw scrolled to; a popover's periods scroll in a column of their own
	function show_top() {
		const $scroller = $root.closest(".es-bottom-sheet .es-filter-panel__picker");
		requestAnimationFrame(() => $scroller.scrollTop(0));
	}

	// a phone has no room for forty fiscal years: one button opens them in a menu under it, the
	// current year first. It is kept across redraws, so focus comes back to it when the menu closes
	const hook_menus = new Map();
	function hook_menu(hook) {
		const is_on = (choice) =>
			!first_day &&
			current?.condition === hook.key &&
			String(current.value) === choice.value;
		let $menu = hook_menus.get(hook.key);
		if (!$menu) {
			$menu = frappe.ui
				.dropdown({
					button: { label: __(hook.label), icon_right: "chevron-down" },
					options: () =>
						hook_choices(hook).map((choice) => ({
							label: choice.label,
							selected: is_on(choice),
							onclick: () => {
								apply(is_on(choice) ? [] : [[hook.key, choice.value]]);
								refresh();
								show_top();
							},
						})),
				})
				.addClass("es-filter-picker__period-menu");
			hook_menus.set(hook.key, $menu);
		}
		const on = hook.choices.find(is_on);
		$menu.find(".es-button__label").text(on ? on.label : __(hook.label));
		return $menu.attr("data-state", on ? "checked" : null);
	}

	// the period holding today first (a `query_value` is its from and to days), then as listed
	function hook_choices(hook) {
		const today = frappe.datetime.get_today();
		const now = hook.choices.find(
			({ query_value: days }) => Array.isArray(days) && days[0] <= today && today <= days[1]
		);
		return now ? [now, ...hook.choices.filter((c) => c !== now)] : hook.choices;
	}

	function draw_periods() {
		// the period clicked keeps focus once redrawn, so the keyboard (and Escape) stays here
		const active = document.activeElement;
		const focused = $periods[0].contains(active) ? active.dataset.key : null;
		$periods.find(".es-filter-picker__period-menu").detach();
		$periods.empty().prop("hidden", condition !== "Between");
		const timespan = !first_day && current?.condition === "Timespan" ? current.value : null;
		const other = timespan && !PERIODS.flat().includes(timespan) ? [[timespan]] : [];
		[...other, ...PERIODS].forEach((group) => {
			const $group = $(
				'<div class="es-filter-picker__period-group flex flex-col gap-0.5"></div>'
			)
				.attr("data-count", group.length)
				.appendTo($periods);
			group.forEach((value) => {
				const label = period_label(value);
				$group.append(period_row(label, timespan === value, ["Timespan", value]));
			});
		});
		for (const hook of hooks.filter((h) => h.choices.length)) {
			const $group = $(
				'<div class="es-filter-picker__period-group flex flex-col gap-0.5"></div>'
			).appendTo($periods);
			if (frappe.is_mobile()) {
				$group.append(hook_menu(hook));
				continue;
			}
			$group.prepend($('<div class="es-menu__group-label"></div>').text(__(hook.label)));
			for (const choice of hook.choices) {
				const active =
					!first_day &&
					current?.condition === hook.key &&
					String(current.value) === choice.value;
				$group.append(period_row(choice.label, active, [hook.key, choice.value]));
			}
		}
		if (focused) {
			$periods
				.find("[data-key]")
				.filter((i, el) => el.dataset.key === focused)
				.trigger("focus");
		}
	}

	async function load_hook(hook) {
		if (hook.choices.length) return;
		const args = {};
		if (hook.depends_on) {
			const rule = (ctx.others || []).find((f) => f[1] === hook.depends_on && f[2] === "=");
			args[hook.depends_on] = rule?.[3];
		}
		// the server says why it failed; the period group just stays out
		configs[hook.key].data = await frappe.xcall(hook.get_field, args).catch(() => null);
		if (gone) return;
		hook.choices = choices_of(configs[hook.key].data);
		draw_periods();
		show_on_calendar();
		show_picked();
		periods_cue();
		// a fiscal year's days are known now; boxes typed into meanwhile keep their text
		if (`${$from.val()}|${$to.val()}` === before) fill_inputs();
	}

	function show_picked() {
		const picked = $periods.find('[data-state="checked"]')[0];
		if (picked) picked.scrollIntoView({ block: "nearest" });
		else $periods.scrollTop(0);
	}

	// the month to show: the one with today when the span runs past it, else the span's last
	function view_date(days) {
		const [from, to] = days || [];
		const end = to || from;
		if (!end) return new Date();
		if (from && from.isSameOrBefore(moment(), "day") && end.isAfter(moment(), "day")) {
			return new Date();
		}
		return end.toDate();
	}

	let calendar;
	// closed: what was typed is saved once, and nothing after touches the calendar
	let gone = false;
	// the first day of a span picked on the calendar, until the second click
	let first_day = null;
	function make_calendar() {
		calendar?.destroy();
		const days = span();
		calendar = new AirDatepicker($calendar[0], {
			inline: true,
			range: condition === "Between",
			toggleSelected: false,
			locale: frappe.ui.form.get_datepicker_locale(),
			firstDay: frappe.datetime.get_first_day_of_the_week_index(),
			selectedDates: (days || []).filter(Boolean).map((d) => d.toDate()),
			startDate: view_date(days),
			onSelect: ({ date }) => {
				const picked = []
					.concat(date)
					.filter(Boolean)
					.map((d) => moment(d).format("YYYY-MM-DD"));
				if (!picked.length) return;
				if (condition !== "Between") {
					apply([[condition, picked[0]]]);
				} else if (picked.length === 1) {
					// two clicks make a span: the first marks where it starts, and filters on that
					// day by itself only if the picker closes before the second
					first_day = picked[0];
					$from.val(show(first_day));
					$to.val("");
					before = `${$from.val()}|${$to.val()}`;
					// a sheet's Apply counts it as a change, as it does a typed date
					$from.trigger("input");
					draw_periods();
					return;
				} else {
					apply([["Between", picked]]);
				}
				fill_inputs();
				draw_periods();
			},
		});
	}

	// after a period or typed dates: the calendar shows them without rebuilding
	function show_on_calendar() {
		if (gone) return;
		const days = (span() || []).filter(Boolean);
		// selecting a day would also turn to its month; the month is set once, below, and a day
		// being pressed keeps it, or the redrawn month loses the click
		calendar.opts.moveToOtherMonthsOnSelect = false;
		calendar.clear({ silent: true });
		if (days.length)
			calendar.selectDate(
				days.map((d) => d.toDate()),
				{ silent: true }
			);
		calendar.opts.moveToOtherMonthsOnSelect = true;
		if (pressing !== "calendar") calendar.setViewDate(view_date(span()));
	}

	function refresh() {
		fill_inputs();
		draw_periods();
		show_on_calendar();
	}

	function draw() {
		$box.find(".es-filter-picker__input").detach();
		$box.children(".es-filter-picker__box-label").remove();
		$from.attr({
			placeholder: condition === "Between" ? __("From") : show(frappe.datetime.get_today()),
			"aria-label": condition === "Between" ? __("From date") : __("Date"),
		});
		const empty_check = is_set_condition(condition);
		if (!empty_check) $box.append(condition === "Between" ? range_boxes($from, $to) : [$from]);
		$body.prop("hidden", empty_check);
		$hint.prop("hidden", !ctx.hint || empty_check);
		show_set_hint($box, df, condition);
		fill_inputs();
		draw_periods();
		show_picked();
		periods_cue();
		make_calendar();
	}

	draw();
	hooks.forEach(load_hook);
	setTimeout(show_picked);
	if (!is_set_condition(condition)) focus_soon($from[0], ctx);
	// the bar calls this when the picker closes, so the calendar goes with its panel; a date
	// typed but not yet entered is kept, as the other pickers keep theirs
	$root[0].destroy = () => {
		if (gone) return;
		if (first_day) apply([["Between", [first_day, first_day]]]);
		else if (`${$from.val()}|${$to.val()}` !== before) commit_typed();
		gone = true;
		calendar?.destroy();
	};
	return $root[0];
}

const number_options = (df) => [
	{ label: __("Between"), value: "Between" },
	{ label: __("Equals"), value: "=" },
	{ label: __("Not equals"), value: "!=" },
	{ label: __("More than"), value: ">" },
	{ label: __("Less than"), value: "<" },
	{ label: __("At least"), value: ">=" },
	{ label: __("At most"), value: "<=" },
	...set_options(df),
];

// a pill clicked again lets go, so none may be picked
// a phone's choices are buttons in even rows, the pick the outline button; wider screens keep
// Tab Buttons. `data-count` sets the rows out
function choice_buttons($row, choices, on_pick) {
	const phone = frappe.is_mobile();
	$row.addClass(phone ? "es-filter-picker__choices" : "es-tab-buttons").attr(
		"data-count",
		choices.length
	);
	for (const choice of choices) {
		const $choice = (
			phone
				? frappe.ui.button({ label: choice.label })
				: $('<button type="button" class="es-pill"></button>').text(choice.label)
		).on("click", () => {
			choice.pick(choice.on());
			on_pick?.();
		});
		$choice[0].is_on = choice.on;
		$row.append($choice);
	}
	mark_choices($row);
}

function mark_choices($row) {
	$row.children().each(function () {
		const on = this.is_on();
		$(this).attr({ "aria-pressed": String(on), "data-state": on ? "active" : "inactive" });
		if (this.classList.contains("es-button"))
			$(this).attr("data-variant", on ? "outline" : null);
	});
}

export function number(ctx) {
	const { df } = ctx;
	if (df.fieldtype === "Duration") return duration(ctx);
	const [rule] = ctx.rules;
	const options = number_options(df);
	// a count or an amount is usually matched exactly; a percent is read in ranges
	const start = df.fieldtype === "Percent" ? "Between" : "=";
	let condition = rule ? condition_of(rule) : start;
	// typed as people count it (stars), saved as the field stores it
	const scale = scale_of(df);
	const rating = df.fieldtype === "Rating";
	// number boxes give "2.5" whatever the site's number format, so they read with Number()
	const shown = (v) => {
		if (is_blank(v)) return "";
		if (rating) return stars_of(df, Number(v));
		return Number(v);
	};
	const [from, to] = rule?.[0] === "Between" ? list_of(rule[1]).map(shown) : [];
	const bounds = df.fieldtype === "Percent" ? [0, 100] : null;
	const unit = { Percent: " %", Rating: " ★" }[df.fieldtype] || "";

	const $root = $('<div class="es-filter-picker es-filter-picker--number"></div>');
	const $from = input_el({
		type: "number",
		placeholder: __("From") + unit,
		label: __("From"),
		value: from ?? "",
	});
	const $to = input_el({
		type: "number",
		placeholder: __("To") + unit,
		label: __("To"),
		value: to ?? "",
	});
	const $value = input_el({
		type: "number",
		placeholder: __("Value") + unit,
		label: __(df.label, null, df.doctype),
		value: rule && !["Between", "is"].includes(rule[0]) ? shown(rule[1]) : "",
	});
	const $box = condition_box(
		{ label: __(df.label, null, df.doctype), options, value: condition },
		(value) => {
			const carried = carried_value(condition, value, {
				value: $value.val(),
				from: $from.val(),
				to: $to.val(),
			});
			if (carried && "value" in carried) $value.val(carried.value);
			else if (carried) {
				$from.val(carried.from);
				$to.val(carried.to);
			}
			condition = value;
			draw();
			save();
		}
	);
	const $extra = $('<div class="es-filter-picker__extra"></div>');
	$root.append($box, $extra);

	const num = (v) => (is_blank(v) ? null : flt(Number(v)));
	const stored = (v) => {
		if (v == null) return "";
		return rating ? rating_of(df, v) : v;
	};
	function save() {
		if (is_set_condition(condition)) return ctx.set(set_rule(condition));
		if (not_whole()) return;
		if (condition === "Between") {
			const [a, b] = in_order(num($from.val()), num($to.val()));
			return ctx.set(a == null && b == null ? [] : [["Between", [stored(a), stored(b)]]]);
		}
		const v = num($value.val());
		ctx.set(v == null ? [] : [[condition, stored(v)]]);
	}
	// a save after typing stops; one still waiting when the picker closes runs then (`flush`)
	const later = frappe.utils.debounce(save, 300);
	// a whole-number field takes no decimals: one typed stays in the box with a line saying why,
	// and nothing is saved until the number is whole again
	const whole = df.fieldtype === "Int";
	const $whole_hint = $('<p class="es-filter-picker__hint" hidden></p>')
		.text(__("{0} takes whole numbers only", [__(df.label, null, df.doctype)]))
		.insertAfter($box);
	// only the boxes shown count: a box the condition hid keeps its text but isn't saved
	const shown_boxes = () =>
		is_set_condition(condition) ? [] : condition === "Between" ? [$from, $to] : [$value];
	const not_whole = () =>
		whole && shown_boxes().some(($i) => !Number.isInteger(Number($i.val() || 0)));
	[$from, $to, $value].forEach(($i) => {
		$i.attr("inputmode", whole ? "numeric" : "decimal");
		if (whole) {
			$i.attr("step", 1).on("keydown", (e) => {
				if (["e", "E"].includes(e.key)) e.preventDefault();
			});
		}
		// a Rating takes whole or half stars, from none up to the field's own count
		if (rating) {
			$i.attr({ min: 0, max: scale, step: 0.5 })
				.on("keydown", (e) => {
					if (["-", "+", "e", "E"].includes(e.key)) e.preventDefault();
				})
				.on("change", () => {
					if ($i.val() !== "") $i.val(shown(stored(num($i.val()))));
				});
		}
		// From after To is the same span (it saves so): once both boxes are left, they read so
		$i.on("blur", (e) => {
			if (condition !== "Between" || [$from[0], $to[0]].includes(e.relatedTarget)) return;
			const [a, b] = [num($from.val()), num($to.val())];
			if (a == null || b == null || a <= b) return;
			const low = $to.val();
			$to.val($from.val());
			$from.val(low);
		});
		$i.on("input", () => {
			// "3." is still being typed: the box reads empty until the next digit
			if ($i[0].validity?.badInput) return;
			const $ranges = $extra.children(".es-filter-picker__ranges");
			if ($ranges.length) mark_choices($ranges);
			$whole_hint.prop("hidden", !not_whole());
			if (not_whole()) return later.cancel();
			if (rating && Number($i.val()) > scale) $i.val(scale);
			later();
		});
	});

	function draw() {
		$box.find(".es-filter-picker__input").detach();
		$box.children(".es-filter-picker__box-label").remove();
		$extra.empty();
		show_set_hint($box, df, condition);
		$whole_hint.prop("hidden", !not_whole());
		if (is_set_condition(condition)) return;
		$box.append(condition === "Between" ? range_boxes($from, $to) : [$value]);
		if (!bounds) return;
		if (condition === "Between") {
			const cuts = [0, 25, 50, 75, 100];
			const $ranges = $('<div class="es-filter-picker__ranges" role="group"></div>')
				.attr("aria-label", __("Common ranges"))
				.appendTo($extra);
			const ranges = cuts.slice(0, -1).map((a, i) => {
				const b = cuts[i + 1];
				return {
					label: `${a}–${b}%`,
					on: () => num($from.val()) === a && num($to.val()) === b,
					pick: (on) => {
						$from.val(on ? "" : a);
						$to.val(on ? "" : b);
						save();
						draw();
						// the redrawn range keeps focus, so the keyboard (and Escape) stays here
						$extra.find(".es-filter-picker__ranges").children().eq(i).trigger("focus");
					},
				};
			});
			choice_buttons($ranges, ranges);
		} else if (["<", ">", "<=", ">="].includes(condition)) {
			const $slider = $('<input type="range" class="es-filter-picker__slider">')
				.attr({
					min: bounds[0],
					max: bounds[1],
					step: 0.5,
					"aria-label": __(df.label, null, df.doctype),
				})
				.val(num($value.val()) ?? bounds[0])
				.on("input", () => {
					$value.val($slider.val());
					paint_kept($slider, bounds, condition);
					later();
				});
			$value.off("input.slider").on("input.slider", () => {
				$slider.val($value.val());
				paint_kept($slider, bounds, condition);
			});
			paint_kept($slider, bounds, condition);
			const $scale = $('<div class="es-filter-picker__scale" aria-hidden="true"></div>');
			// each mark sits where the knob does at that value
			[0, 25, 50, 75, 100].forEach((n) =>
				$scale.append(
					$("<span></span>")
						.text(`${n}%`)
						.css("--at", n / 100)
				)
			);
			$extra.append($slider, $scale);
		}
	}

	draw();
	focus_soon((condition === "Between" ? $from : $value)[0], ctx);
	$root[0].destroy = later.flush;
	return $root[0];
}

// parts of the day a time filter offers at once; each stays within one day
const DAY_PARTS = () => [
	[__("Morning"), "06:00", "11:59"],
	[__("Afternoon"), "12:00", "16:59"],
	[__("Evening"), "17:00", "20:59"],
];

const show_time = (hhmm) => {
	const time = moment(hhmm, "HH:mm");
	return hhmm && time.isValid() ? time.format("HH:mm") : hhmm || "";
};

/**
 * A typed time as "HH:mm": "9", "930", "0930" or "9:30".
 * Null for an empty box, undefined for one that isn't a time.
 */
function read_time(text) {
	const t = String(text || "").trim();
	if (!t) return null;
	const digits = /^\d{1,4}$/.exec(t) && t.padStart(t.length <= 2 ? 2 : 4, "0");
	const [h, m] = digits ? [+digits.slice(0, 2), +(digits.slice(2) || 0)] : [];
	if (digits)
		return h < 24 && m < 60 ? moment({ hour: h, minute: m }).format("HH:mm") : undefined;
	const time = moment(t, ["H:mm", "HH:mm"], true);
	return time.isValid() ? time.format("HH:mm") : undefined;
}

/** A time of day: a date's conditions without its calendar, and parts of the day for a range. */
export function time(ctx) {
	const { df } = ctx;
	const [rule] = ctx.rules;
	const options = [
		{ label: __("Between"), value: "Between" },
		{ label: __("At"), value: "=" },
		{ label: __("Before"), value: "<" },
		{ label: __("After"), value: ">" },
		{ label: __("At or before"), value: "<=" },
		{ label: __("At or after"), value: ">=" },
		...set_options(df),
	];
	let condition = rule ? condition_of(rule) : "Between";
	// the server keeps seconds too; the box shows hours and minutes
	const shown = (v) => (is_blank(v) ? "" : show_time(String(v).slice(0, 5)));
	const [from, to] = rule?.[0] === "Between" ? list_of(rule[1]).map(shown) : [];

	const $root = $('<div class="es-filter-picker es-filter-picker--number"></div>');
	const box = (placeholder, label, value) =>
		input_el({ placeholder, label, value: value ?? "" }).attr("inputmode", "numeric");
	const $from = box(__("From"), __("From"), from);
	const $to = box(__("To"), __("To"), to);
	const $value = box(
		__("Time"),
		__(df.label, null, df.doctype),
		rule && !["Between", "is"].includes(rule[0]) ? shown(rule[1]) : ""
	);
	const $box = condition_box(
		{ label: __(df.label, null, df.doctype), options, value: condition },
		(value) => {
			const carried = carried_value(condition, value, {
				value: $value.val(),
				from: $from.val(),
				to: $to.val(),
			});
			if (carried && "value" in carried) $value.val(carried.value);
			else if (carried) {
				$from.val(carried.from);
				$to.val(carried.to);
			}
			condition = value;
			draw();
			save();
		}
	);
	const $error = $('<p class="es-filter-picker__error" role="alert" hidden></p>');
	const $extra = $('<div class="es-filter-picker__extra"></div>');
	$root.append($box, $error, $extra);

	const boxes = () => (condition === "Between" ? [$from, $to] : [$value]);
	function show_error($bad, text) {
		$from.add($to).add($value).removeAttr("aria-invalid");
		$bad?.attr("aria-invalid", "true");
		$error.text(text || "").prop("hidden", !$bad);
	}
	// a box it can't read, or a range across midnight, saves nothing and says why
	function save() {
		if (is_set_condition(condition)) return show_error(), ctx.set(set_rule(condition));
		const $bad = boxes().find(($i) => read_time($i.val()) === undefined);
		if ($bad) {
			return show_error(
				$bad,
				__("Can't read {0}. Type a time like {1}.", [$bad.val(), show_time("09:30")])
			);
		}
		if (condition === "Between") {
			const [a, b] = [read_time($from.val()), read_time($to.val())];
			if (a && b && a > b) {
				return show_error($to, __("A time range can't cross midnight."));
			}
			show_error();
			return ctx.set(a == null && b == null ? [] : [["Between", [a || "", b || ""]]]);
		}
		show_error();
		const v = read_time($value.val());
		ctx.set(v ? [[condition, v]] : []);
	}
	const later = frappe.utils.debounce(save, 300);
	$from
		.add($to)
		.add($value)
		.on("input", () => {
			const $parts = $extra.children(".es-filter-picker__ranges");
			if ($parts.length) mark_choices($parts);
			later();
		})
		// "930" becomes "09:30"
		.on("blur", function () {
			const read = read_time(this.value);
			if (read) this.value = show_time(read);
			later.flush();
		});

	function draw() {
		$box.find(".es-filter-picker__input").detach();
		$box.children(".es-filter-picker__box-label").remove();
		$extra.empty();
		show_set_hint($box, df, condition);
		if (is_set_condition(condition)) return;
		$box.append(condition === "Between" ? range_boxes($from, $to) : [$value]);
		if (condition !== "Between") return;
		const $parts = $('<div class="es-filter-picker__ranges" role="group"></div>')
			.attr("aria-label", __("Parts of the day"))
			.appendTo($extra);
		choice_buttons(
			$parts,
			DAY_PARTS().map(([label, a, b]) => ({
				label,
				on: () => read_time($from.val()) === a && read_time($to.val()) === b,
				pick: (on) => {
					$from.val(on ? "" : show_time(a));
					$to.val(on ? "" : show_time(b));
					save();
					mark_choices($parts);
				},
			}))
		);
		$parts.children().each(function (i) {
			const [, a, b] = DAY_PARTS()[i];
			frappe.ui.tooltip($(this), { text: `${show_time(a)} – ${show_time(b)}` });
		});
	}

	draw();
	focus_soon((condition === "Between" ? $from : $value)[0], ctx);
	$root[0].destroy = later.flush;
	return $root[0];
}

// the slider fills the side the filter keeps: past the knob for "at least", up to it for "at most";
// the knob's centre sits half its width in from each end
function paint_kept($slider, [min, max], condition) {
	const share = (Number($slider.val()) - min) / (max - min);
	const at = `calc(var(--knob-size) / 2 + (100% - var(--knob-size)) * ${share})`;
	const above = [">", ">="].includes(condition);
	$slider[0].style.setProperty("--kept-start", above ? at : "0%");
	$slider[0].style.setProperty("--kept-end", above ? "100%" : at);
}

const MINUTE = 60;
const HOUR = 3600;
const DAY = 24 * HOUR;
// the ruler's marks sit evenly, not to scale, so minutes and hours both get room
const TIME_MARKS = [0, 15, 30, 60, 120, 240, 480, 1440].map((m) => m * MINUTE);
const TIME_PRESETS = TIME_MARKS.slice(1);
const TIME_RANGES = [
	[0, 15],
	[15, 60],
	[60, 240],
	[240, 480],
	[480, 1440],
].map(([a, b]) => [a * MINUTE, b * MINUTE]);
const time_step = (s) => (s < HOUR ? 5 * MINUTE : s < 4 * HOUR ? 15 * MINUTE : 30 * MINUTE);

// where a time sits along the ruler, from 0 to 1; a day or more sits at the end
function time_place(s) {
	const last = TIME_MARKS.length - 1;
	if (s >= DAY) return 1;
	let i = 0;
	while (s > TIME_MARKS[i + 1]) i++;
	return (i + (s - TIME_MARKS[i]) / (TIME_MARKS[i + 1] - TIME_MARKS[i])) / last;
}

function time_at(place) {
	const last = TIME_MARKS.length - 1;
	const x = Math.min(Math.max(place, 0), 1) * last;
	const i = Math.min(last - 1, Math.floor(x));
	const s = TIME_MARKS[i] + (x - i) * (TIME_MARKS[i + 1] - TIME_MARKS[i]);
	return Math.round(s / time_step(s)) * time_step(s);
}

// hours and minutes, as the form's Duration field takes them
function duration_input(label, get, set) {
	const $group = $('<span class="es-filter-picker__duration" role="group"></span>').attr(
		"aria-label",
		label
	);
	const part = (name, unit) => {
		const $input = $(
			'<input class="es-filter-picker__segment" inputmode="numeric" autocomplete="off" placeholder="0">'
		).attr("aria-label", `${label} ${name}`);
		const $unit = $('<span class="es-filter-picker__unit" aria-hidden="true"></span>');
		$group.append($input, $unit.text(unit));
		return $input;
	};
	const $hours = part(__("hours"), __("h", null, "Hours (Field: Duration)"));
	const $minutes = part(__("minutes"), __("m", null, "Minutes (Field: Duration)"));
	// each box as wide as its digits, so "1 h 30 m" reads as one time
	const fit = (input) => (input.style.width = `${Math.max(input.value.length, 1)}ch`);
	$group.fill = () => {
		const s = get();
		const { hours, minutes } = frappe.utils.seconds_to_duration(s, { hide_days: true });
		$hours.val(s == null ? "" : hours);
		$minutes.val(s == null ? "" : minutes);
		fit($hours[0]);
		fit($minutes[0]);
	};
	$hours
		.add($minutes)
		.on("input", function () {
			this.value = this.value.replace(/\D/g, "");
			fit(this);
			const seconds = frappe.utils.duration_to_seconds(
				0,
				cint($hours.val()),
				cint($minutes.val())
			);
			// a box emptied with only zeros left beside it empties the side; a 0 typed stays 0
			set(this.value === "" && !seconds ? null : seconds);
		})
		.on("blur", $group.fill)
		// the 0 filled in beside a typed hour is replaced by what is typed, not added to
		.on("focus", function () {
			setTimeout(
				() => this === document.activeElement && this.value === "0" && this.select()
			);
		});
	// the box's empty room types the hours, as a plain input would
	$group.on("click", (e) => e.target === $group[0] && $hours.trigger("focus"));
	$group.fill();
	$group.first_input = $hours;
	return $group;
}

/**
 * A ruler from 0 to a day: the part the filter keeps is filled, and knobs mark its times. Drag
 * a knob, click the ruler or a mark, or use the arrow keys; `pick(key, seconds, done)` gets each
 * change, `done` once the person lets go.
 */
function time_ruler({ label, state, pick }) {
	const $ruler = $('<div class="es-filter-picker__ruler"></div>');
	const $track = $('<div class="es-filter-picker__track" aria-hidden="true"></div>');
	const kept = [0, 1].map(() =>
		$('<div class="es-filter-picker__kept" aria-hidden="true"></div>')
	);
	const knobs = [0, 1].map(() =>
		$('<span class="es-filter-picker__knob" role="slider" tabindex="0"></span>')
			.attr({ "aria-valuemin": 0, "aria-valuemax": DAY })
			.append('<span class="es-filter-picker__knob-time" aria-hidden="true"></span>')
	);
	$ruler.append($track, ...kept, ...knobs);

	// a click picks the nearer end of a range, or the empty one on its side
	const nearest = (s) => {
		const { condition, from, to } = state();
		if (condition !== "Between") return "value";
		if (from == null && to == null) return "from";
		if (to == null) return s >= from ? "to" : "from";
		if (from == null) return s <= to ? "from" : "to";
		return Math.abs(s - from) <= Math.abs(s - to) ? "from" : "to";
	};
	// a range's ends don't cross
	const within = (key, s) => {
		const { from, to } = state();
		s = Math.max(s, 0);
		if (key === "from" && to != null) return Math.min(s, to);
		if (key === "to" && from != null) return Math.max(s, from);
		return s;
	};
	const choose = (s, done) => {
		const key = nearest(s);
		pick(key, within(key, s), done);
	};

	TIME_MARKS.forEach((s) => {
		$('<button type="button" class="es-filter-picker__mark"></button>')
			.text(time_text(s))
			.css("inset-inline-start", `${time_place(s) * 100}%`)
			.on("click", () => choose(s, true))
			.appendTo($ruler);
	});

	const time_of = (e) => {
		const box = $track[0].getBoundingClientRect();
		const place = (e.clientX - box.left) / box.width;
		return time_at(frappe.utils.is_rtl() ? 1 - place : place);
	};
	$ruler[0].addEventListener("pointerdown", (e) => {
		const bare = [$ruler, $track, ...kept].some(($part) => $part[0] === e.target);
		if (bare) choose(time_of(e), true);
	});
	let dragging = null;
	knobs.forEach(($knob) => {
		const knob = $knob[0];
		knob.addEventListener("pointerdown", (e) => {
			e.preventDefault();
			dragging = $knob.attr("data-key");
			$ruler.attr("data-dragging", "");
			knob.setPointerCapture(e.pointerId);
			knob.focus();
		});
		knob.addEventListener("pointermove", (e) => {
			if (dragging) pick(dragging, within(dragging, time_of(e)), false);
		});
		const drop = () => {
			if (!dragging) return;
			// a resting knob let go without a move sets nothing
			if (state()[dragging] != null) pick(dragging, state()[dragging], true);
			dragging = null;
			$ruler.removeAttr("data-dragging");
		};
		knob.addEventListener("pointerup", drop);
		knob.addEventListener("pointercancel", drop);
		knob.addEventListener("keydown", (e) => {
			const key = $knob.attr("data-key");
			const s = state()[key] ?? 0;
			const forward = frappe.utils.is_rtl() ? "ArrowLeft" : "ArrowRight";
			const back = forward === "ArrowLeft" ? "ArrowRight" : "ArrowLeft";
			const next = {
				[forward]: s + time_step(s),
				ArrowUp: s + time_step(s),
				[back]: s - time_step(Math.max(s - 1, 0)),
				ArrowDown: s - time_step(Math.max(s - 1, 0)),
				PageUp: s + HOUR,
				PageDown: s - HOUR,
				Home: 0,
				End: DAY,
			}[e.key];
			if (next == null) return;
			e.preventDefault();
			pick(key, within(key, next), false);
		});
	});

	$ruler.update = () => {
		const { condition, value, from, to } = state();
		const at = (s) => (s == null ? null : time_place(s));
		const gap = 0.02;
		let spans = [];
		if (condition === "Between") {
			if (from != null || to != null) spans = [[at(from) ?? 0, at(to) ?? 1]];
		} else if (value != null) {
			const v = at(value);
			spans = {
				">": [[v, 1]],
				">=": [[v, 1]],
				"<": [[0, v]],
				"<=": [[0, v]],
				"!=": [
					[0, Math.max(v - gap, 0)],
					[Math.min(v + gap, 1), 1],
				],
			}[condition] || [[v, v]];
		}
		kept.forEach(($kept, i) => {
			const [a, b] = spans[i] || [0, 0];
			$kept.attr("data-empty", b > a ? null : "").css({
				"inset-inline-start": `${a * 100}%`,
				width: `${(b - a) * 100}%`,
			});
		});
		// knobs close together put their times on their outer sides, so the two don't overlap
		const apart = from != null && to != null ? (at(to) - at(from)) * $track[0].offsetWidth : 0;
		$ruler.attr(
			"data-close",
			condition === "Between" && apart < 56 && from != null && to != null ? "" : null
		);
		const keys = condition === "Between" ? ["from", "to"] : ["value"];
		knobs.forEach(($knob, i) => {
			const key = keys[i];
			$knob.prop("hidden", !key);
			if (!key) return;
			const s = state()[key];
			// an end not set yet rests at 0: an empty range's two knobs sit as one
			const name = { from: __("From"), to: __("To") }[key] || label;
			$knob
				.attr({
					"data-key": key,
					"data-empty": s == null ? "" : null,
					"aria-label": name,
					"aria-valuenow": s ?? null,
					"aria-valuetext": s == null ? null : time_text(s),
				})
				.css("inset-inline-start", `${time_place(s ?? 0) * 100}%`)
				.attr("data-not", condition === "!=" ? "" : null)
				.children()
				.text(s == null ? "" : time_text(s));
		});
	};
	return $ruler;
}

export function duration(ctx) {
	const { df } = ctx;
	const [rule] = ctx.rules;
	let condition = rule ? condition_of(rule) : "Between";
	const seconds = (v) => (is_blank(v) ? null : cint(v));
	const [from, to] = rule?.[0] === "Between" ? list_of(rule[1]).map(seconds) : [];
	const times = {
		value: rule && !["Between", "is"].includes(rule[0]) ? seconds(rule[1]) : null,
		from: from ?? null,
		to: to ?? null,
	};

	const $root = $('<div class="es-filter-picker es-filter-picker--number"></div>');
	const $box = condition_box(
		{ label: __(df.label, null, df.doctype), options: number_options(df), value: condition },
		(value) => {
			const carried = carried_value(condition, value, times);
			for (const [key, s] of Object.entries(carried || {}))
				times[key] = is_blank(s) ? null : s;
			if (carried) Object.values(inputs).forEach((input) => input.fill());
			condition = value;
			draw();
			save();
		}
	);
	const inputs = {};
	const typed = (key) => (s) => {
		times[key] = s;
		$ruler.update();
		mark_choices($choices);
		later();
	};
	inputs.value = duration_input(
		__(df.label, null, df.doctype),
		() => times.value,
		typed("value")
	);
	inputs.from = duration_input(__("From"), () => times.from, typed("from"));
	inputs.to = duration_input(__("To"), () => times.to, typed("to"));

	const $ruler = time_ruler({
		label: __(df.label, null, df.doctype),
		state: () => ({ condition, ...times }),
		pick: (key, s, done) => {
			times[key] = s;
			inputs[key].fill();
			$ruler.update();
			mark_choices($choices);
			if (done) save();
			else later();
		},
	});
	const $choices = $(
		'<div class="es-filter-picker__ranges es-filter-picker__times mt-3" role="group"></div>'
	);
	const $extra = $('<div class="es-filter-picker__extra"></div>').append($ruler, $choices);
	$root.append($box, $extra);

	function save() {
		if (is_set_condition(condition)) return ctx.set(set_rule(condition));
		if (condition === "Between") {
			const [from, to] = in_order(times.from, times.to);
			return ctx.set(
				from == null && to == null ? [] : [["Between", [from ?? "", to ?? ""]]]
			);
		}
		ctx.set(times.value == null ? [] : [[condition, times.value]]);
	}
	const later = frappe.utils.debounce(save, 300);

	function draw_choices() {
		const between = condition === "Between";
		$choices.empty().attr("aria-label", between ? __("Common ranges") : __("Common times"));
		const choices = between
			? TIME_RANGES.map(([a, b]) => ({
					label: a ? `${time_text(a)}–${time_text(b)}` : __("Under {0}", [time_text(b)]),
					on: () => times.from === a && times.to === b,
					pick: (on) => Object.assign(times, { from: on ? null : a, to: on ? null : b }),
			  }))
			: TIME_PRESETS.map((s) => ({
					label: time_text(s),
					on: () => times.value === s,
					pick: (on) => (times.value = on ? null : s),
			  }));
		choice_buttons($choices, choices, () => {
			Object.values(inputs).forEach(($input) => $input.fill());
			$ruler.update();
			mark_choices($choices);
			save();
		});
	}

	function draw() {
		$box.children(".es-filter-picker__duration").detach();
		$box.children(".es-filter-picker__box-label").remove();
		show_set_hint($box, df, condition);
		const empty_check = is_set_condition(condition);
		$extra.prop("hidden", empty_check);
		if (empty_check) return;
		$box.append(
			condition === "Between" ? range_boxes(inputs.from, inputs.to) : [inputs.value]
		);
		draw_choices();
		$ruler.update();
	}

	draw();
	focus_soon((condition === "Between" ? inputs.from : inputs.value).first_input[0], ctx);
	$root[0].destroy = later.flush;
	return $root[0];
}

/**
 * The Duration icon with a hand that turns to a time: the minutes set its angle, and an hour more
 * or less adds a turn (two at most, so a big jump stays readable). `turn(null)` puts it back.
 */
export function stopwatch() {
	const $icon =
		$(`<svg class="icon icon-sm es-filter-stopwatch" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
		<line x1="10" x2="14" y1="2" y2="2" />
		<circle cx="12" cy="14" r="8" />
		<line class="es-filter-stopwatch__hand" x1="12" x2="12" y1="14" y2="9.76" />
	</svg>`);
	const hand = $icon.find(".es-filter-stopwatch__hand")[0];
	const REST = 45;
	let angle = REST;
	let last = null;
	hand.style.transform = `rotate(${REST}deg)`;
	$icon[0].turn = (s) => {
		const target = s == null ? REST : ((s % HOUR) / HOUR) * 360;
		const hours =
			s != null && last != null ? Math.floor(s / HOUR) - Math.floor(last / HOUR) : 0;
		const turns = Math.max(-2, Math.min(2, hours));
		let next = Math.floor(angle / 360) * 360 + target + turns * 360;
		if (!turns && next - angle > 180) next -= 360;
		if (!turns && angle - next > 180) next += 360;
		angle = next;
		last = s;
		hand.style.transform = `rotate(${angle}deg)`;
	};
	return $icon[0];
}

export function text(ctx) {
	const { df } = ctx;
	const [rule] = ctx.rules;
	const options = [
		{ label: __("Contains"), value: "like" },
		{ label: __("Doesn't contain"), value: "not like" },
		{ label: __("Equals"), value: "=" },
		{ label: __("Not equals"), value: "!=" },
		...set_options(df),
	];
	// a big table matches a whole value unless the person chose otherwise, as its rows do
	const large = df.fieldtype === "Data" && frappe.get_meta(ctx.doctype)?.is_large_table;
	// a barcode is read whole, from a scanner or a label
	let condition = ctx.condition || (large || df.fieldtype === "Barcode" ? "=" : "like");
	if (rule) condition = condition_of(rule);
	const $root = $('<div class="es-filter-picker es-filter-picker--text"></div>');
	const $input = input_el({
		placeholder: __("Type to filter"),
		label: __(df.label, null, df.doctype),
		value:
			!rule || rule[0] === "is"
				? ""
				: rule[0].includes("like")
				? strip_like(rule[1])
				: rule[1],
	});
	const save = () => {
		if (is_set_condition(condition)) return ctx.set(set_rule(condition));
		const text = $input.val().trim();
		const like = condition.includes("like");
		ctx.set(text ? [[condition, like ? `%${text}%` : text]] : []);
	};
	const scan = barcode_scanner(df, (code) => {
		$input.val(code);
		save();
	});
	const show_value = (value) => {
		$input.add(scan.$button).prop("hidden", is_set_condition(value));
		if (is_set_condition(value)) scan.stop();
	};
	const $box = condition_box(
		{ label: __(df.label, null, df.doctype), options, value: condition },
		(value) => {
			condition = value;
			show_value(value);
			show_set_hint($box, df, value);
			if (["like", "="].includes(value)) ctx.remember?.(value);
			save();
		}
	);
	const later = frappe.utils.debounce(save, 250);
	$input.on("input", () => later());
	show_value(condition);
	$root.append($box.append($input, scan.$button), scan.$area);
	show_set_hint($box, df, condition);
	if (ctx.hint) $root.append($('<p class="es-filter-picker__hint"></p>').text(ctx.hint));
	focus_soon($input[0], ctx);
	$root[0].destroy = () => {
		scan.stop();
		later.flush();
	};
	return $root[0];
}

export function check(ctx) {
	const [rule] = ctx.rules;
	let value = rule ? cint(rule[1]) : null;
	const $root = $(
		'<div class="es-filter-picker es-filter-picker--check" role="radiogroup"></div>'
	).attr("aria-label", __(ctx.df.label));
	const draw = (focus_index = null) => {
		$root.empty();
		[
			[1, __("Yes")],
			[0, __("No")],
		].forEach(([v, label], index) => {
			$('<button type="button" class="es-menu__item" role="radio"></button>')
				.attr("aria-checked", value === v ? "true" : "false")
				.append(
					'<span class="es-combobox__radio" aria-hidden="true"></span>',
					$('<span class="es-menu__label"></span>').text(label)
				)
				.on("click", () => {
					// a radio stays picked; Clear or the chip's × takes it off
					if (value === v) return;
					value = v;
					ctx.set([["=", value]]);
					// the option pressed keeps focus once redrawn, so the keyboard stays here
					draw(index);
				})
				.appendTo($root);
		});
		if (focus_index != null) $root.children().eq(focus_index).trigger("focus");
	};
	draw();
	arrow_keys($root[0], ".es-menu__item");
	return $root[0];
}

// a filter the picker can't show: what it is, one line per condition, and where to edit it
export function advanced_notice(ctx, lines, on_edit) {
	const $root = $('<div class="es-filter-picker es-filter-picker--notice"></div>');
	$root.append(
		...lines.map((line) => $('<p class="m-0 text-base text-ink-gray-8"></p>').text(line))
	);
	// the button says where to change them; without one, a line does
	$root.append(
		on_edit
			? frappe.ui.button({
					label: __("Edit in Advanced filters"),
					icon_right: "arrow-right",
					css_class: "es-filter-picker__forward",
					onclick: on_edit,
			  })
			: $('<p class="m-0 text-p-sm text-ink-gray-5"></p>').text(
					__("These conditions can be changed in Advanced filters.")
			  )
	);
	return $root[0];
}
