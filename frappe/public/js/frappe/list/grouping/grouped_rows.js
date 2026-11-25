import { get_currency_doc, get_currency_field, get_ranked_field, get_total_field } from "./totals";

// a group loads at most this many rows (or sub-groups) a page: grouped rows aren't virtualized
const MAX_PAGE_LENGTH = 500;
// on a phone a big group stops loading on scroll after this many, so the next group stays in reach
const AUTO_LOAD_LIMIT = 100;
// the list's checkboxes hold names as text; a DocType with number names sends numbers
const name_of = (doc) => String(doc.name);

/** A grouped list: a row per group with its count and totals; groups and rows load a page at a time. */
export default class GroupedRows {
	constructor(list) {
		this.list = list;
		this.uid = 0;
		this.reset();
		this.setup_events();
	}

	get levels() {
		return this.list.grouping.levels;
	}

	/** With `keep_open` (the same levels, only how they show changed) open groups stay open with their rows. */
	reset({ keep_open = false, keep_figures = false } = {}) {
		this.stop_observing();
		this.near_loads = new Set();
		this.has_more = false;
		this.next_start = 0;
		this.empty_pending = false;
		if (keep_open) {
			if (!keep_figures) this.drop_figures();
			return;
		}
		this.figures_token = (this.figures_token || 0) + 1;
		this.totals = null;
		this.figures_key = null;
		this.list.$result.find(".list-group-section, .list-group-total").remove();
		this.list.$result.parent()[0]?.style.removeProperty("--list-group-levels");
		this.groups = [];
		this.nodes = new Map();
		this.open_state = new Map();
		// depth → open, after an Alt-click or Expand all: groups loaded later follow it too
		this.level_open = new Map();
		this.loaded_counts = new Map();
		this.rows_key = null;
	}

	/** Totals asked for another way leave the screen until the new ones come. */
	drop_figures() {
		this.figures_token++;
		this.totals = null;
		this.figures_key = null;
		for (const node of this.nodes.values()) node.totals = {};
		this.list.$result.find(".list-group-total").remove();
		this.list.$result.find(".list-group-row .list-row-col:not(.list-subject)").empty();
	}

	stop_observing() {
		this.observers?.forEach((observer) => observer.disconnect());
		this.observers = new Set();
		this.visible_observer?.disconnect();
		this.visible_observer = null;
		this.near = new Set();
	}

	setup_events() {
		const $result = this.list.$result;
		$result.off(".list-grouping");
		$result.on("click.list-grouping", ".list-group-row", (e) => {
			if ($(e.target).closest(".select-like").length) return;
			const node = this.node_of(e.currentTarget);
			if (!node) return;
			// the arrow is a button so a tap finds it, but the row keeps the keyboard's place
			if (e.target.closest(".list-group-toggle"))
				e.currentTarget.focus({ preventScroll: true });
			this.toggle(node, { whole_level: e.altKey });
		});
		$result.on("keydown.list-grouping", ".list-group-row", (e) => {
			const node = this.node_of(e.currentTarget);
			const open = { Enter: !node?.open, ArrowRight: true, ArrowLeft: false }[e.key];
			if (!node || open === undefined || e.target !== e.currentTarget) return;
			e.preventDefault();
			e.stopPropagation();
			// Left on a closed sub-group goes up to its parent, as in a tree
			if (e.key === "ArrowLeft" && !node.open && !e.altKey && node.depth) {
				this.focus_group_of(node.$group.parent()[0]);
			} else if (e.altKey) {
				this.set_level_open(node.depth, open);
				this.sync_toggle_all();
			} else if (open !== node.open) {
				this.toggle(node);
			}
		});
		// on click, before the list's change handler ticks the rows on screen and syncs the boxes
		$result.on("click.list-grouping", ".list-group-checkbox", (e) => {
			const node = this.node_of(e.target);
			if (node) this.select_group(node, e.target.checked);
		});
		// a grey box says why on a tap too, not only on hover: a phone has no hover
		$result.on("click.list-grouping", ".list-group-row .select-like", (e) => {
			const box = e.currentTarget.querySelector(".list-group-checkbox");
			if (box?.disabled && this.node_of(box)?.count) {
				frappe.ui.toast({
					message: e.currentTarget.title,
					type: "info",
					duration: 3000,
					id: "list-group-disabled",
				});
			}
		});
		$result.on(
			"keydown.list-grouping",
			".list-group-body .list-row-container:not(.list-group-row)",
			(e) => {
				if (e.key !== "ArrowLeft" || e.altKey || e.target !== e.currentTarget) return;
				e.preventDefault();
				this.focus_group_of(e.currentTarget);
			}
		);
		// a record assigned to two users shows in both their groups: its copies tick together
		$result.on("change.list-grouping", ".list-row-checkbox", (e) => {
			const name = this.list.get_checkbox_docname($(e.target));
			const checked = this.list.checked_docnames.has(name);
			this.list.find_checkbox_by_docname(name).each((_, checkbox) => {
				checkbox.checked = checked;
			});
		});
		// after the list has ticked the group's own rows
		$result.on("change.list-grouping", ".list-group-checkbox", (e) => {
			const list = this.list;
			// a record shared with another ticked group stays ticked
			if (!e.target.checked) {
				this.still_selected?.forEach((node) => (node.selected = true));
				this.still_selected = null;
				for (const node of this.nodes.values()) {
					if (node.selected)
						this.rows_under(node).forEach((doc) =>
							list.checked_docnames.add(name_of(doc))
						);
				}
			}
			$result.find(".list-row-checkbox").each((_, checkbox) => {
				checkbox.checked = list.checked_docnames.has(
					list.get_checkbox_docname($(checkbox))
				);
			});
			list.on_row_checked();
		});
		$result.on("click.list-grouping", ".list-group-toggle-all", (e) => {
			e.stopPropagation();
			this.set_all_open(!this.all_open());
		});
	}

	node_of(el) {
		return this.nodes.get(el.closest(".list-group-section")?.dataset.groupId);
	}

	level_under(parent) {
		return this.levels[parent ? parent.depth + 1 : 0];
	}

	is_nested(node) {
		return node.depth < this.levels.length - 1;
	}

	focus_group_of(el) {
		$(el).closest(".list-group-section").children(".list-group-row").trigger("focus");
	}

	get_call_args() {
		return this.group_request(null, this.list.start, this.group_page_length());
	}

	/** The list's own reportview.get with a GROUP BY, so a group counts the rows the list shows. */
	group_request(parent, start, page_length) {
		const list = this.list;
		const { fieldname, order } = this.level_under(parent);
		const filters = this.filters_for(parent);
		const at_once = this.loads_at_once(fieldname);
		// a field with many values loads its groups page by page, and its empty group apart
		if (!at_once) filters.push([list.doctype, fieldname, "is", "set"]);
		const ranked_total = this.ranked_total();
		const order_by = {
			"value-desc": `${fieldname} desc`,
			"count-desc": `count desc, ${fieldname} asc`,
			"sum-desc": ranked_total ? `total_${ranked_total} desc, ${fieldname} asc` : null,
		}[order];
		// groups that come at once come a row per currency; a page of groups tells one currency from many
		const split = at_once ? this.split_fields() : [];
		const group_by = [...new Set([fieldname, ...split])];
		return {
			method: "frappe.desk.reportview.get",
			args: {
				doctype: list.doctype,
				fields: [
					...group_by,
					{ COUNT: "*", as: "count" },
					...this.total_fields(),
					...(at_once ? [] : this.currency_range_fields()),
				],
				filters,
				group_by: group_by.join(", "),
				order_by: (!at_once && order_by) || `${fieldname} asc`,
				start: at_once ? 0 : start,
				// Assigned To needs every set of users; one more than a page tells whether there is a next one
				page_length:
					fieldname === "_assign" || split.length
						? 0
						: at_once
						? MAX_PAGE_LENGTH
						: page_length + 1,
				with_link_titles: 1,
			},
		};
	}

	/** A page of groups from a `group_request` response: `{ items, has_more }`. */
	groups_of(message, depth, page_length) {
		const { fieldname } = this.levels[depth];
		const rows = this.list.rows_of(message);
		if (fieldname === "_assign")
			return { items: this.assignee_groups(rows, depth), has_more: false };

		const df = frappe.meta.get_docfield(this.list.doctype, fieldname);
		const link_doctype = df?.fieldtype === "Link" && df.options;
		let items = this.merge_by_value(
			rows.map((row) => ({
				value: row[fieldname] ?? "",
				count: row.count,
				totals: this.totals_of(row),
				title: link_doctype && frappe.utils.get_link_title(link_doctype, row[fieldname]),
			}))
		);
		const options = this.option_values(fieldname);
		if (!options) {
			const has_more = items.length > page_length;
			return { items: items.slice(0, page_length), has_more };
		}

		const empty = items.filter((group) => group.value === "");
		items = items.filter((group) => group.value !== "");
		if (this.list.grouping.show_empty) {
			const seen = new Set(items.map((group) => group.value));
			for (const value of this.allowed_options(fieldname, options)) {
				if (!seen.has(value)) items.push({ value, count: 0, totals: {} });
			}
		}
		// NULL and "" are both no value
		const merged = empty.length ? this.merge_groups(empty) : null;
		return {
			items: this.with_empty(this.sort_groups(items, depth), merged, depth),
			has_more: false,
		};
	}

	/** A record assigned to many users counts in each user's group. */
	assignee_groups(rows, depth) {
		const by_user = new Map();
		const empty = [];
		for (const row of rows) {
			const group = { value: "", count: row.count, totals: this.totals_of(row) };
			const users = JSON.parse(row._assign || "[]");
			// the Not assigned group lists records with no value at all ("is not set")
			if (!row._assign) empty.push(group);
			for (const user of users) by_user.set(user, [...(by_user.get(user) || []), group]);
		}
		const items = [...by_user].map(([user, groups]) => ({
			...this.merge_groups(groups),
			value: user,
		}));
		const merged = empty.length ? this.merge_groups(empty) : null;
		return this.with_empty(this.sort_groups(items, depth), merged, depth);
	}

	sort_groups(groups, depth) {
		const { fieldname, order } = this.levels[depth];
		const options = this.option_values(fieldname);
		const position = (group) => {
			const index = options.indexOf(group.value);
			return index === -1 ? options.length : index;
		};
		const by_value = options
			? (a, b) => position(a) - position(b)
			: (a, b) =>
					frappe
						.user_info(a.value)
						.fullname.localeCompare(frappe.user_info(b.value).fullname);
		const rank = this.rank_of(depth);
		if (rank) return groups.sort((a, b) => rank(b) - rank(a) || by_value(a, b));
		return groups.sort(order === "value-desc" ? (a, b) => by_value(b, a) : by_value);
	}

	/** How "Most rows first" and "Highest total first" rank a group; null for the value orders. */
	rank_of(depth) {
		const { order } = this.levels[depth];
		const ranked_total = this.ranked_total();
		if (order === "count-desc") return (group) => group.count;
		if (order === "sum-desc" && ranked_total)
			return (group) => group.totals[ranked_total] || 0;
		return null;
	}

	/** By rank when groups are ranked, else last; -1 while it belongs on a page not loaded yet. */
	empty_index(groups, empty, depth, has_more) {
		const rank = this.rank_of(depth);
		const index = rank ? groups.findIndex((group) => rank(group) < rank(empty)) : -1;
		return index !== -1 || has_more ? index : groups.length;
	}

	with_empty(groups, empty, depth) {
		if (empty) groups.splice(this.empty_index(groups, empty, depth, false), 0, empty);
		return groups;
	}

	merge_groups(groups) {
		const count = groups.reduce((sum, group) => sum + group.count, 0);
		const totals = {};
		for (const [field, fn] of this.shown_totals()) {
			if (this.currency_field(field)) {
				totals[field] = this.merge_currencies(
					groups.map((group) => group.totals[field]),
					fn
				);
				continue;
			}
			const present = groups.filter((group) => group.totals[field] != null);
			const weight = (group) => (fn === "avg" ? group.count : 1);
			const sum = present.reduce((s, group) => s + group.totals[field] * weight(group), 0);
			const weights = present.reduce((s, group) => s + weight(group), 0);
			totals[field] = !present.length ? null : fn === "avg" ? sum / weights : sum;
		}
		return { value: "", count, totals };
	}

	/** Figures per currency added up: undefined while one of them is still on its way. */
	merge_currencies(figures, fn) {
		if (figures.includes(undefined)) return undefined;
		const merged = {};
		for (const [currency, { value, count }] of figures.flatMap((f) =>
			Object.entries(f || {})
		)) {
			merged[currency] ||= { value: 0, count: 0 };
			merged[currency].value += fn === "avg" ? value * count : value;
			merged[currency].count += count;
		}
		if (fn === "avg") Object.values(merged).forEach((part) => (part.value /= part.count));
		return Object.keys(merged).length ? merged : null;
	}

	/** Rows that came apart for the same value (a row per currency) as one group. */
	merge_by_value(items) {
		const by_value = new Map();
		for (const item of items)
			by_value.set(item.value, [...(by_value.get(item.value) || []), item]);
		return [...by_value.values()].map((same) =>
			same.length === 1
				? same[0]
				: { ...same[0], ...this.merge_groups(same), value: same[0].value }
		);
	}

	loads_at_once(fieldname) {
		return fieldname === "_assign" || Boolean(this.option_values(fieldname));
	}

	/** The options the list's filters on this field still let through. */
	allowed_options(fieldname, options) {
		const { doctype } = this.list;
		return this.list
			.get_filters_for_args()
			.reduce((values, [filter_doctype, field, op, value]) => {
				if (filter_doctype !== doctype || field !== fieldname) return values;
				const list = Array.isArray(value)
					? value
					: frappe.ui.filter_utils.split_values(String(value ?? ""));
				const listed = list.map((v) => String(v).trim());
				if (op === "=") return values.filter((v) => v === value);
				if (op === "!=") return values.filter((v) => v !== value);
				if (op === "in") return values.filter((v) => listed.includes(v));
				if (op === "not in") return values.filter((v) => !listed.includes(v));
				return values;
			}, options);
	}

	/** The options of a Select field; null for a field with many values. */
	option_values(fieldname) {
		const df = frappe.meta.get_docfield(this.list.doctype, fieldname);
		if (df?.fieldtype === "Select") return (df.options || "").split("\n").filter(Boolean);
		return null;
	}

	/** The grouping's totals for the list's columns: `[fieldname, "sum" | "avg"]`. */
	shown_totals() {
		const { doctype } = this.list;
		const columns = new Set(this.field_columns().map((df) => df.fieldname));
		const readable = (field) => {
			const df = frappe.meta.get_docfield(doctype, field);
			return df && frappe.views.ListView.can_read_field(doctype, df);
		};
		// a count still on its way when the list is ungrouped reads the totals too
		return Object.entries(this.list.grouping?.totals || {}).filter(([field]) => {
			if (!columns.has(field) || !readable(field) || !this.total_field(field)) return false;
			// amounts in many currencies add up apart, by a currency the user can read
			const currency = this.currency_field(field);
			return !currency || readable(currency);
		});
	}

	/** The DocFields of the list's field columns, the ones that show totals. */
	field_columns() {
		return this.list.columns.filter((col) => col.type === "Field").map((col) => col.df);
	}

	total_fields() {
		return this.shown_totals().map(([field, fn]) => ({
			[fn.toUpperCase()]: this.total_field(field).fieldname,
			as: `total_${field}`,
		}));
	}

	total_field(fieldname) {
		const { doctype } = this.list;
		const df = frappe.meta.get_docfield(doctype, fieldname);
		return df && get_total_field(doctype, df, this.list.get_filters_for_args());
	}

	/** The field holding each record's currency when a total adds up amounts in many currencies. */
	currency_field(fieldname) {
		return get_currency_field(this.list.doctype, this.total_field(fieldname));
	}

	split_fields() {
		return [
			...new Set(this.shown_totals().map(([field]) => this.currency_field(field))),
		].filter(Boolean);
	}

	currency_range_fields() {
		return this.split_fields().flatMap((field) => [
			{ MIN: field, as: `min_${field}` },
			{ MAX: field, as: `max_${field}` },
			{ COUNT: field, as: `count_${field}` },
		]);
	}

	/** The total "Highest total first" ranks by. */
	ranked_total() {
		return get_ranked_field(
			this.list.doctype,
			this.field_columns(),
			Object.fromEntries(this.shown_totals()),
			this.list.get_filters_for_args()
		)?.fieldname;
	}

	/** An amount in many currencies is `{ [currency]: { value, count } }`, undefined until its figures come. */
	totals_of(row) {
		return Object.fromEntries(
			this.shown_totals().map(([field]) => {
				const value = row[`total_${field}`];
				const currency_field = this.currency_field(field);
				if (!currency_field || value == null) return [field, value];
				const [min, max] = [row[`min_${currency_field}`], row[`max_${currency_field}`]];
				// rows with no currency beside rows with one make two currencies
				const with_currency = row[`count_${currency_field}`];
				const one =
					currency_field in row ||
					(min === max && (!with_currency || with_currency === row.count));
				// an amount with no currency is in the system's
				const currency =
					(currency_field in row ? row[currency_field] : min) ||
					frappe.boot.sysdefaults.currency;
				return [field, one ? { [currency]: { value, count: row.count } } : undefined];
			})
		);
	}

	lacks_currencies(group) {
		return this.split_fields().length > 0 && Object.values(group.totals).includes(undefined);
	}

	fetch_currencies(groups, parent) {
		if (!groups.length) return Promise.resolve();
		const { doctype } = this.list;
		const { fieldname } = this.level_under(parent);
		const group_by = [...new Set([fieldname, ...this.split_fields()])];
		const filters = [
			...this.filters_for(parent),
			[doctype, fieldname, "in", groups.map((group) => group.value)],
		];
		const args = {
			doctype,
			fields: [...group_by, { COUNT: "*", as: "count" }, ...this.total_fields()],
			filters,
			group_by: group_by.join(", "),
			page_length: 0,
		};
		return Promise.resolve(frappe.call({ method: "frappe.desk.reportview.get", args })).then(
			(r) => {
				const rows = this.list.rows_of(r.message);
				for (const group of groups) {
					const own = rows.filter((row) => row[fieldname] === group.value);
					group.totals = this.merge_groups(
						own.map((row) => ({ count: row.count, totals: this.totals_of(row) }))
					).totals;
				}
			}
		);
	}

	load_currencies(nodes) {
		if (!nodes.length) return;
		const { groups, figures_token } = this;
		this.fetch_currencies(nodes, null)
			.then(() => {
				if (this.groups !== groups || this.figures_token !== figures_token) return;
				nodes.forEach((node) => this.redraw_totals(node));
				this.fit_labels();
			})
			// frappe.call has shown the error: the cells show nothing, not a loading bar for good
			.catch(() => {
				if (this.groups !== groups || this.figures_token !== figures_token) return;
				for (const node of nodes) {
					for (const [field, value] of Object.entries(node.totals)) {
						if (value === undefined) node.totals[field] = null;
					}
					this.redraw_totals(node);
				}
			});
	}

	redraw_totals(node) {
		const $row = node.$group?.children(".list-group-row");
		if (!$row?.[0]?.isConnected) return;
		for (const [field] of this.shown_totals()) {
			if (!this.currency_field(field)) continue;
			$row.find(`.list-row-col[data-fieldname="${field}"]`).html(
				this.total_html(frappe.meta.get_docfield(this.list.doctype, field), node.totals)
			);
		}
		this.add_currency_tooltips($row);
	}

	prepare_data(r) {
		const { fieldname } = this.levels[0];
		const at_once = this.loads_at_once(fieldname);
		const first_page = this.list.start === 0 || at_once;
		const page_length = this.group_page_length();
		const { items, has_more } = this.groups_of(r.message, 0, page_length);
		// loaded rows stay only while they still answer the list's filters and sort
		const rows_key = this.get_rows_key();
		const same_rows = rows_key === this.rows_key;
		this.rows_key = rows_key;
		// figures answer the filters alone: a new sort keeps them, a new filter drops them
		const figures_key = JSON.stringify(this.filters_for(null));
		const same_figures = figures_key === this.figures_key;
		this.figures_key = figures_key;
		const previous = first_page ? this.nodes : new Map();
		const old_nodes = same_rows ? previous : new Map();
		if (first_page) {
			if (!same_figures) this.totals = null;
			if (!same_rows) this.loaded_counts = new Map();
			this.groups = [];
			this.nodes = new Map();
			this.load_totals();
		}
		// every row has no value: the empty group's count is still on its way
		this.empty_pending = first_page && !items.length && !at_once;
		this.has_more = has_more;
		this.next_start = this.list.start + page_length;
		const offset = this.groups.length;
		const added = items.map((group, i) =>
			this.make_node(group, null, offset + i, first_page ? items : null)
		);
		const lacking = added.filter((node) => this.lacks_currencies(node));
		added.forEach((node) => {
			this.keep_loaded(node, old_nodes.get(node.id));
			// the last figures show until the new ones come, so the cells don't blink
			const old = same_figures ? previous.get(node.id) : null;
			for (const [field, value] of Object.entries(node.totals)) {
				if (value === undefined) node.totals[field] = old?.totals[field];
			}
		});
		this.load_currencies(lacking);
		this.groups.push(...added);
		this.appended = first_page ? null : added;
		// a ranked empty group comes with the first page and shows once its page has come
		const ranked = Boolean(this.rank_of(0));
		if (first_page) this.empty_group = null;
		if (!at_once && ranked && !first_page) {
			this.insert_empty(this.empty_group);
		} else if (!at_once && (ranked || !has_more)) {
			// the empty group stays where it was until its new count comes
			const old_empty = old_nodes.get(this.id_of([{ fieldname, value: "" }]));
			this.insert_empty(old_empty, old_empty);
			this.add_empty_group(old_nodes);
		}
		this.sync_data();
	}

	/** A scroll page of groups adds its groups after the ones drawn; false when all must be drawn again. */
	append_groups() {
		const added = this.appended;
		this.appended = null;
		if (!added?.length) return false;
		const $result = this.list.$result;
		const drawn = $result
			.children(".list-group-section")
			.get()
			.map((section) => section.dataset.groupId);
		const before = this.groups.slice(0, -added.length);
		const in_place =
			this.groups.slice(-added.length).every((node, i) => node === added[i]) &&
			before.length === drawn.length &&
			before.every((node, i) => node.id === drawn[i]);
		if (!in_place) return false;
		const $groups = $(added.map((node) => this.make_group(node)[0]));
		const $total = $result.children(".list-group-total");
		if ($total.length) $groups.insertBefore($total);
		else $result.append($groups);
		this.fit_added($groups);
		this.fit_labels();
		this.after_groups_change();
		return true;
	}

	/** The list's row query: rows loaded for another one no longer belong in the groups. */
	get_rows_key() {
		const { start, page_length, ...args } = this.list.get_args();
		return JSON.stringify(args);
	}

	/** At most `MAX_PAGE_LENGTH` groups a page; a refresh gets back every group drawn. */
	group_page_length() {
		const paged = this.groups.filter((group) => group.value !== "").length;
		return Math.min(this.list.page_length, Math.max(MAX_PAGE_LENGTH, paged));
	}

	load_totals() {
		if (!this.total_fields().length) {
			this.totals = null;
			return;
		}
		const { groups, figures_token } = this;
		this.fetch_figures(this.filters_for(null))
			.then(({ totals }) => {
				if (this.groups !== groups || this.figures_token !== figures_token) return;
				this.totals = totals;
				this.render_total_row();
			})
			.catch(() => {});
	}

	/** The count and totals over `filters` as one group. */
	fetch_figures(filters) {
		const split = this.split_fields();
		const args = {
			doctype: this.list.doctype,
			fields: [...split, { COUNT: "*", as: "count" }, ...this.total_fields()],
			filters,
			...(split.length && { group_by: split.join(", "), page_length: 0 }),
		};
		return Promise.resolve(frappe.call({ method: "frappe.desk.reportview.get", args })).then(
			(r) => {
				const groups = this.list
					.rows_of(r.message)
					.map((row) => ({ count: row.count, totals: this.totals_of(row) }));
				if (split.length) return this.merge_groups(groups);
				return groups[0] || { count: 0, totals: {} };
			}
		);
	}

	/** The rows with no value at the level under `parent`: a group of its own, or null. */
	fetch_empty_group(parent) {
		const { fieldname } = this.level_under(parent);
		const filters = [...this.filters_for(parent), this.filter_of({ fieldname, value: "" })];
		return this.fetch_figures(filters).then(({ count, totals }) =>
			count ? { value: "", count, totals } : null
		);
	}

	add_empty_group(old_nodes) {
		const { groups, figures_token } = this;
		const empty_id = this.id_of([{ fieldname: this.levels[0].fieldname, value: "" }]);
		this.fetch_empty_group(null)
			.catch(() => null)
			.then((group) => {
				if (this.groups !== groups) return;
				if (group && this.figures_token !== figures_token) group.totals = {};
				this.empty_group = group;
				this.empty_pending = false;
				const $result = this.list.$result;
				$result.find(".list-group-pending").remove();
				const kept = this.nodes.get(empty_id);
				const place =
					kept?.$group?.[0].contains(document.activeElement) && this.remember_place();
				if (kept && groups.includes(kept)) {
					groups.splice(groups.indexOf(kept), 1);
					this.nodes.delete(kept.id);
					kept.$group?.remove();
				}
				const node = this.insert_empty(group, kept || old_nodes.get(empty_id));
				if (node) {
					const $group = this.make_group(node);
					const $next = groups[groups.indexOf(node) + 1]?.$group;
					const $total = $result.find(".list-group-total");
					if ($next?.[0].isConnected) $group.insertBefore($next);
					else if ($total.length) $group.insertBefore($total);
					else $result.append($group);
					this.fit_added($group);
				}
				if (place) this.restore_place({ ...place, top: null });
				this.sync_data();
				this.render_total_row();
				this.list.toggle_result_area();
				this.fit_labels();
				this.after_groups_change();
				this.list.render_count();
			});
	}

	/** Null when the empty group is in already, or belongs on a later page. */
	insert_empty(group, old = null) {
		if (!group || this.groups.some((node) => node.value === "")) return null;
		const index = this.empty_index(this.groups, group, 0, this.has_more);
		if (index === -1) return null;
		const { value, count, totals } = group;
		const node = this.make_node({ value, count, totals }, null, index);
		// "First" has opened a group already: one that comes later opens only if none has
		const decided =
			this.level_open.has(0) ||
			this.groups.concat(node).some((g) => this.open_state.has(g.id));
		if (!decided && this.list.grouping.open === "first") {
			node.open = Boolean(count) && !this.groups.some((other) => other.open);
		}
		this.keep_loaded(node, old);
		this.groups.splice(index, 0, node);
		return node;
	}

	/** A refresh shows what a group had loaded until it loads again, so rows don't jump and a selection stays. */
	keep_loaded(node, old) {
		if (!old) return;
		// a group ticked before its rows came still ticks them
		node.selected = old.selected;
		if (!old.rows && !old.children) return;
		Object.assign(node, {
			rows: old.rows,
			children: old.children,
			has_more: old.has_more,
			next_start: old.next_start,
			stale: true,
		});
		const adopt = (nodes) =>
			nodes?.forEach((child) => {
				child.stale = Boolean(child.rows || child.children);
				this.nodes.set(child.id, child);
				adopt(child.children);
			});
		adopt(node.children);
	}

	make_node(group, parent, index, siblings = null) {
		const depth = parent ? parent.depth + 1 : 0;
		const fieldname = this.levels[depth].fieldname;
		const path = [...(parent?.path || []), { fieldname, value: group.value }];
		const id = this.id_of(path);
		const node = {
			...group,
			id,
			uid: ++this.uid,
			fieldname,
			depth,
			path,
			index,
			rows: null,
			children: null,
			has_more: false,
			loading: false,
			selected: Boolean(parent?.selected),
		};
		node.open = this.open_state.get(id) ?? this.default_open(node, siblings);
		this.nodes.set(id, node);
		return node;
	}

	default_open(node, siblings) {
		if (this.level_open.has(node.depth)) return this.level_open.get(node.depth);
		const open = this.list.grouping.open;
		// "First" opens the first group with rows: an empty one kept by Show empty groups has none
		const first = siblings?.findIndex((group) => group.count > 0) ?? 0;
		return open === "all" || (open === "first" && node.index === first);
	}

	/** The list's rows are every row loaded so far, closed groups too, so a selection survives. */
	sync_data() {
		this.list.data = this.groups
			.flatMap((node) => this.rows_under(node))
			.uniqBy((doc) => doc.name);
	}

	filters_for(node) {
		return [...this.list.get_filters_for_args(), ...(node ? this.filters_of(node) : [])];
	}

	filters_of(node) {
		return node.path.map((step) => this.filter_of(step));
	}

	filter_of({ fieldname, value }) {
		const doctype = this.list.doctype;
		if (value === "") return [doctype, fieldname, "is", "not set"];
		return [doctype, fieldname, "=", value];
	}

	render() {
		this.stop_observing();
		this.note_column_widths();
		const $result = this.list.$result;
		$result.find(".list-group-section, .list-group-total, .list-group-pending").remove();
		$result.append(this.groups.map((node) => this.make_group(node)));
		if (!this.groups.length && this.empty_pending) {
			$result.append(this.list.get_loading_rows(3).addClass("list-group-pending"));
		}
		this.render_total_row();
		this.hide_grouped_columns($result);
		this.after_groups_change();
	}

	remember_place() {
		const active = document.activeElement;
		const row = this.list.$result[0].contains(active)
			? active.closest(".list-row-container")
			: null;
		const group = row?.closest(".list-group-section")?.dataset.groupId;
		const root = this.scroll_box();
		const place = { top: root.scrollTop, group };
		if (group && !row.classList.contains("list-group-row")) {
			place.name = this.list.get_checkbox_docname($(row).find(".list-row-checkbox"));
		}
		return place;
	}

	restore_place(place) {
		if (!place) return;
		if (place.top != null) this.scroll_box().scrollTop = place.top;
		const node = place.group && this.nodes.get(place.group);
		if (!node?.$group?.[0].isConnected) return;
		const $row = place.name
			? node.$body
					.find(".list-row-checkbox")
					.filter((_, el) => this.list.get_checkbox_docname($(el)) === place.name)
					.closest(".list-row-container")
			: node.$group.children(".list-group-row");
		$row[0]?.focus({ preventScroll: true });
	}

	after_groups_change() {
		this.set_sticky_tops();
		this.sync_toggle_all();
		this.sync_group_checks();
	}

	/** Group rows come before any row: they take the widths rows give their columns. */
	note_column_widths() {
		const list = this.list;
		if (frappe.is_mobile()) return;
		for (const col of list.columns) {
			const width = cint(col.df?.width);
			if (!width) continue;
			const { fieldname } = list.get_header_cell(col);
			list.column_max_widths[fieldname] = Math.max(
				flt(list.column_max_widths[fieldname]) || 0,
				width
			);
		}
	}

	make_group(node) {
		if (node.$body) {
			this.visible_observer?.unobserve(node.$body[0]);
			this.near.delete(node.$body[0]);
		}
		node.$group = $('<div class="list-group-section"></div>').attr({
			"data-group-id": node.id,
			"data-depth": node.depth,
		});
		node.$group[0].style.setProperty("--list-group-depth", node.depth);
		node.$body = $(`<div class="list-group-body list-group-body-${node.uid}"></div>`);
		const $collapse = $('<div class="list-group-collapse"></div>').append(node.$body);
		node.$group.append(this.make_group_row(node), $collapse).toggleClass("is-open", node.open);
		if (node.open) this.open_body(node);
		return node.$group;
	}

	/** Lets a group's label run over the empty cells beside it, up to the first total, with its count after it. */
	fit_labels() {
		// a hidden list (a form is open over it) measures every row as 0 wide
		if (!this.list.$result.is(":visible")) return;
		const rows = [...this.list.$result[0].querySelectorAll(".list-group-row")];
		const rtl = getComputedStyle(this.list.$result[0]).direction === "rtl";
		// every row measured first, then every label set: one layout, not one per row
		const fits = rows.map((row) => {
			const label = row.querySelector(".list-group-label");
			const count = label.nextElementSibling;
			const stop =
				[...row.querySelectorAll(".level-left > .list-row-col:not(.list-subject)")].find(
					(cell) => cell.offsetParent && cell.textContent.trim()
				) || row.querySelector(".level-right");
			const [l, s] = [label.getBoundingClientRect(), stop.getBoundingClientRect()];
			const room = rtl ? l.right - s.right : s.left - l.left;
			// a count hidden by the last fit kept the room it takes
			if (count.offsetWidth) {
				const c = count.getBoundingClientRect();
				count.dataset.space = rtl ? l.left - c.left : c.right - l.right;
			}
			const width = room - (Number(count.dataset.space) || 0) - 16;
			// a label squeezed below its name's start drops the count instead
			const squeezed = width < Math.min(label.scrollWidth, 64);
			return { width: Math.max(squeezed ? room - 16 : width, 0), squeezed };
		});
		rows.forEach((row, i) => {
			const label = row.querySelector(".list-group-label");
			label.style.setProperty("--list-group-label-width", `${fits[i].width}px`);
			label.nextElementSibling.classList.toggle("hidden", fits[i].squeezed);
		});
		this.fit_figures();
	}

	/** A figure in many currencies that doesn't fit its column goes into the +N, so no figure is cut. */
	fit_figures() {
		const cells = [...this.list.$result[0].querySelectorAll(".list-group-currencies")];
		const cut = cells.map((cell) =>
			[...cell.querySelectorAll(".list-group-figure:not(.hidden)")].some(
				(figure) => figure.scrollWidth > figure.clientWidth
			)
		);
		cells.forEach((cell, i) => {
			const shown = cell.querySelectorAll(".list-group-figure:not(.hidden)");
			if (!cut[i] || shown.length < 2) return;
			shown[shown.length - 1].classList.add("hidden");
			const more = cell.querySelector(".list-group-more");
			const hidden = cell.querySelectorAll(".list-group-figure.hidden").length;
			more.classList.remove("hidden");
			more.querySelector(".es-badge__label").textContent = `+${hidden}`;
		});
	}

	make_group_row(node) {
		const $row = $(
			this.row_html((fieldname) => this.subject_cell(node, fieldname), node.totals)
		)
			.addClass("list-group-row")
			.attr({ "aria-expanded": node.open, "aria-level": node.depth + 1 });
		this.add_currency_tooltips($row);
		return $row;
	}

	add_currency_tooltips($row) {
		$row.find(".list-group-currencies").each((_, el) => {
			new frappe.ui.Tooltip(el, {
				text: el.dataset.figures,
				text_align: "start",
				class: "list-group-figures-tip",
			});
		});
	}

	/** A layout without the title column puts the subject cell in the first column. */
	row_html(subject_cell, totals) {
		const list = this.list;
		const subject_index = Math.max(
			list.columns.findIndex((col) => col.type === "Subject"),
			0
		);
		const fns = Object.fromEntries(this.shown_totals());
		const cells = list.columns.map((col, i) => {
			const { classes, fieldname } = list.get_header_cell(col);
			if (i === subject_index) return subject_cell(fieldname);
			const total = col.type === "Field" ? this.total_html(col.df, totals, fns) : "";
			return `<div class="${classes}" data-fieldname="${fieldname}">${total}</div>`;
		});
		return list.get_list_row_html_skeleton(cells.join("") + list.get_spacer_cells(), "");
	}

	id_of(path) {
		return JSON.stringify(path.map((step) => [step.fieldname, step.value]));
	}

	hide_grouped_columns($scope) {
		const grouping = this.list.grouping;
		const hidden = new Set(
			grouping.hide_grouped_columns ? this.levels.map((l) => l.fieldname) : []
		);
		// the list's status column shows the status field
		if (hidden.has("status")) hidden.add("status_field");
		$scope.find(".list-row-col[data-fieldname]:not(.list-subject)").each((_, cell) => {
			cell.classList.toggle("list-group-hidden-col", hidden.has(cell.dataset.fieldname));
		});
		// a phone shows the status column as a pill at the row's end
		$scope.find(".level-right .es-badge[data-filter]").each((_, badge) => {
			const fieldname = badge.dataset.filter.split(",")[0];
			badge.classList.toggle(
				"list-group-hidden-col",
				hidden.has("status_field") || hidden.has(fieldname)
			);
		});
	}

	render_total_row() {
		const $result = this.list.$result;
		$result.find(".list-group-total").remove();
		if (!this.groups.length || !Object.values(this.totals || {}).some((v) => v != null))
			return;
		const $row = this.make_total_row();
		$result.append($row);
		this.fit_added($row);
		this.fit_figures();
	}

	fit_added($rows) {
		const list = this.list;
		this.hide_grouped_columns($rows);
		if (!frappe.is_mobile()) list.apply_column_widths($rows);
		// loading rows have no right side to measure
		list.sync_right_width($rows.not(".list-loading-row"));
		// the list drops that border when it does not scroll sideways (update_listview_classes)
		if (list.$result[0].querySelector(".list-row .level-right.border-0")) {
			$rows.find(".list-row .level-right").addClass("border-0");
		}
	}

	make_total_row() {
		// the room of a group row's checkbox and chevron, so "Total" starts where the labels do
		const room = frappe.ui.skeleton.html({ css_class: "invisible list-checkbox-room" });
		const subject = (fieldname) =>
			`<div class="list-row-col ellipsis list-subject level" data-fieldname="${fieldname}">
				<span class="level-item select-like">${room}</span>
				<span class="level-item list-group-toggle me-1 invisible">${frappe.utils.icon(
					"chevron-right",
					"sm"
				)}</span>
				<span class="level-item">${__("Total")}</span>
			</div>`;
		const $row = $(this.row_html(subject, this.totals))
			.removeAttr("tabindex")
			.addClass("list-group-total");
		this.add_currency_tooltips($row);
		return $row;
	}

	subject_cell(node, fieldname) {
		const label = this.label_html(node);
		// a deep grouping has many labels: the tooltip says which field each one is
		const title = frappe.utils.escape_html(
			__("{0}: {1}", [
				frappe.meta.get_translated_label(this.list.doctype, node.fieldname),
				this.label_text(node),
			])
		);
		const select = frappe.utils.escape_html(__("Select the loaded rows of this group"));
		// justify-start: a long label is cut at its end, not centred and cut at both
		return `<div class="list-row-col ellipsis list-subject level" data-fieldname="${fieldname}">
			<span class="level-item select-like" title="${select}">
				<input type="checkbox" class="list-group-checkbox" data-parent="list-group-body-${
					node.uid
				}" aria-label="${select}">
			</span>
			<button type="button" class="level-item list-group-toggle btn-reset me-1 text-ink-gray-6" tabindex="-1" aria-hidden="true">${frappe.utils.icon(
				"chevron-right",
				"sm"
			)}</button>
			<span class="level-item list-group-label justify-start gap-2 ellipsis text-ink-gray-8" title="${title}">${label}</span>
			<span class="level-item ms-2 shrink-0 text-ink-gray-5">${format_number(node.count, null, 0)}</span>
		</div>`;
	}

	label_html(node) {
		const { fieldname, value } = node;
		const escape = frappe.utils.escape_html;
		const text = this.label_text(node);
		if (value === "") {
			// "Not assigned" starts where the names after the avatars (xs, 16px) do
			const room = this.is_user_field(fieldname)
				? '<span class="size-4 shrink-0" aria-hidden="true"></span>'
				: "";
			return `${room}<span class="ellipsis text-ink-gray-6">${escape(text)}</span>`;
		}
		if (this.is_user_field(fieldname)) {
			const user = frappe.user_info(value);
			return `${frappe.ui.avatar.html({
				label: user.fullname,
				image: user.image,
				size: "xs",
			})}<span class="ellipsis">${escape(text)}</span>`;
		}
		const df = frappe.meta.get_docfield(this.list.doctype, fieldname);
		if (df?.fieldtype === "Select") {
			return frappe.ui.badge.html({
				label: text,
				theme: this.badge_theme(fieldname, value),
			});
		}
		return `<span class="ellipsis">${escape(text)}</span>`;
	}

	label_text(node) {
		const { doctype } = this.list;
		const { fieldname, value } = node;
		if (value === "") return fieldname === "_assign" ? __("Not assigned") : __("Not Set");
		if (this.is_user_field(fieldname)) return frappe.user_info(value).fullname;
		const df = frappe.meta.get_docfield(doctype, fieldname);
		// as the list's rows show a Select value, and a Link to a translated DocType
		const translated =
			df?.fieldtype === "Select" ||
			(df?.fieldtype === "Link" && frappe.boot.translated_doctypes?.includes(df.options));
		return translated ? __(node.title || value) : node.title || value;
	}

	is_user_field(fieldname) {
		const df = frappe.meta.get_docfield(this.list.doctype, fieldname);
		return ["owner", "_assign"].includes(fieldname) || df?.options === "User";
	}

	/** A status group takes its rows' Status badge colour; other values get one from their text. */
	badge_theme(fieldname, value) {
		const { doctype } = this.list;
		if (fieldname === "status") {
			// a submittable document is Draft or Cancelled by its docstatus
			const docstatus = { Draft: 0, Cancelled: 2 }[value] ?? 1;
			const indicator = frappe.get_indicator({ doctype, status: value, docstatus }, doctype);
			if (indicator?.[0] === __(value, null, doctype)) return indicator[1];
		}
		return frappe.utils.guess_colour(value);
	}

	total_html(df, totals, fns = Object.fromEntries(this.shown_totals())) {
		const fn = fns[df.fieldname];
		const value = totals?.[df.fieldname];
		const split = fn && this.currency_field(df.fieldname);
		// figures per currency come a moment after the groups
		if (split && value === undefined) {
			return frappe.ui.skeleton.html({
				width: "64px",
				height: "12px",
				css_class: "ms-auto",
			});
		}
		if (!fn || value == null) return "";
		const source = this.total_field(df.fieldname);
		if (split) return this.currencies_html(source, fn, value);
		// an average of whole numbers has decimals
		const field =
			fn === "avg" && source.fieldtype === "Int"
				? { ...source, fieldtype: "Float" }
				: source;
		const doc = get_currency_doc(source, this.list.get_filters_for_args());
		let text = frappe.format(value, field, { inline: true }, doc);
		if (df.fieldtype === "Percent") text = `${format_number(value, null, 0)}%`;
		else if (field.fieldtype === "Int") text = format_number(value, null, 0);
		return fn === "avg" ? __("avg {0}", [text]) : text;
	}

	/** Two short figures then +N, the system currency first, then A to Z on every row. */
	currencies_html(df, fn, figures) {
		const home = frappe.boot.sysdefaults.currency;
		const parts = Object.entries(figures).sort(
			([a], [b]) => (b === home) - (a === home) || a.localeCompare(b)
		);
		const exact = ([currency, { value }]) =>
			frappe.format(value, df, { inline: true }, { [df.options]: currency });
		const avg = (text) => (fn === "avg" ? __("avg {0}", [text]) : text);
		if (parts.length === 1) return avg(exact(parts[0]));

		// short only with a unit (K, L, Cr…): a smaller figure is shown whole
		const short = (part) => {
			const [currency, { value }] = part;
			const [number, unit] = String(
				frappe.utils.shorten_number(value, frappe.boot.sysdefaults.country, 5)
			).split(" ");
			return unit ? `${format_currency(parseFloat(number), currency)} ${unit}` : exact(part);
		};
		const rows = (count) =>
			count === 1 ? __("1 row") : __("{0} rows", [format_number(count, null, 0)]);
		const figures_text = [
			__("{0} by currency", [
				frappe.meta.get_translated_label(this.list.doctype, df.fieldname),
			]),
			...parts.map((part) => `${strip_html(exact(part))} · ${rows(part[1].count)}`),
		].join("\n");
		const escape = frappe.utils.escape_html;
		const spans = parts.map(
			(part, i) =>
				`<span class="list-group-figure truncate min-w-0${i > 1 ? " hidden" : ""}">${short(
					part
				)}</span>`
		);
		const more = parts.length - 2;
		const badge = `<span class="list-group-more shrink-0${
			more > 0 ? "" : " hidden"
		}">${frappe.ui.badge.html({ label: `+${Math.max(more, 0)}`, size: "sm" })}</span>`;
		return `<span class="list-group-currencies flex items-center justify-end gap-2 min-w-0" data-figures="${escape(
			figures_text
		)}"><span class="sr-only">${escape(figures_text)}</span>${avg(
			`<span class="flex items-center justify-end gap-2 min-w-0" aria-hidden="true">${spans.join(
				" "
			)}${badge}</span>`
		)}</span>`;
	}

	open_body(node) {
		if (!node.count && !node.children) node.rows ||= [];
		this.render_body(node);
		if (node.loading || node.failed) return;
		if (node.stale || (!node.rows && !node.children)) this.load_when_visible(node);
	}

	/** A group opened again draws its first page only, unless rows past it are ticked. */
	keep_first_page(node) {
		const step = this.row_step();
		if (node.loading || !(node.rows?.length > step)) return;
		const checked = this.list.checked_docnames;
		if (node.rows.slice(step).some((doc) => checked.has(name_of(doc)))) return;
		node.rows = node.rows.slice(0, step);
		node.has_more = true;
		node.next_start = step;
		node.auto_load_limit = null;
		this.loaded_counts.set(node.id, step);
	}

	/** Expand all on a big grouping loads the groups on screen, and the others as they scroll in. */
	load_when_visible(node) {
		this.visible_observer ??= new IntersectionObserver(
			(entries) => {
				for (const { target, isIntersecting } of entries) {
					if (isIntersecting) this.near.add(target);
					else this.near.delete(target);
				}
				this.load_near();
			},
			{ root: this.scroll_root(), rootMargin: "100% 0px" }
		);
		this.visible_observer.observe(node.$body[0]);
	}

	/** Loads the open groups near the screen three at a time, top first. */
	load_near() {
		const waiting = [...this.near].sort(
			(a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top
		);
		for (const body of waiting) {
			if (this.near_loads.size >= 3) return;
			this.near.delete(body);
			this.visible_observer.unobserve(body);
			const node = this.node_of(body);
			if (!node?.open || !(node.stale || (!node.rows && !node.children))) continue;
			this.near_loads.add(node);
			this.load(node).finally(() => {
				this.near_loads.delete(node);
				// the rows just drawn may have pushed the waiting groups off the screen
				for (const waiting_body of this.near) {
					this.visible_observer?.unobserve(waiting_body);
					this.visible_observer?.observe(waiting_body);
				}
				this.near.clear();
			});
		}
	}

	/** What scrolls the list: its own box, or on a phone the page. */
	scroll_root() {
		return frappe.is_mobile()
			? this.list.$result.closest(".main-section")[0]
			: this.list.$result.parent(".result-container")[0];
	}

	scroll_box() {
		return this.scroll_root() || document.scrollingElement;
	}

	row_step() {
		return Math.min(this.list.selected_page_count, MAX_PAGE_LENGTH);
	}

	render_body(node) {
		const place = node.$body[0].contains(document.activeElement) && this.remember_place();
		node.$body.empty();
		this.add_to_body(node, node.children || node.rows || []);
		if (place) this.restore_place({ ...place, top: null });
	}

	add_to_body(node, items) {
		const list = this.list;
		const $body = node.$body;
		this.stop_end_observer(node);
		$body.children(".list-group-tail").remove();
		const $items = node.children
			? $(items.map((child) => this.make_group(child)[0]))
			: $(items.map((doc) => list.get_list_row_html(doc)).join(""));
		$body.append($items);
		const empty = !node.rows && !node.children;
		const pending = !node.failed && (empty || node.loading_more);
		$body.attr("aria-busy", pending ? "true" : null);
		if (pending) {
			// as many as the rows or sub-groups on their way, so nothing moves when they come;
			// groups opened together show a few each until they load
			const nested = this.is_nested(node);
			const options = nested && this.option_values(this.levels[node.depth + 1].fieldname);
			const coming = nested ? options?.length || 2 : Math.min(node.count, this.row_step());
			const count = empty && !this.batching ? coming : 2;
			const $loading = list.get_loading_rows(count).addClass("list-group-tail");
			// sub-groups on their way are as tall as group rows, not as a phone's two-line rows
			if (nested && empty) $loading.addClass("list-group-loading-groups");
			$body.append($loading);
		}
		const loaded = (node.rows || node.children || []).length;
		if (!pending && (!loaded || node.failed)) {
			$body.append(this.message_html(node));
		}
		if (node.has_more && !node.loading && !node.failed) {
			const limit = frappe.is_mobile() ? node.auto_load_limit || AUTO_LOAD_LIMIT : Infinity;
			if (loaded < limit) this.observe_end(node);
			else $body.append(this.load_more_html(node, loaded));
		}

		this.fit_added($items.add($body.children(".list-group-tail")));
		if (node.selected && !node.children) {
			items.forEach((doc) => list.checked_docnames.add(name_of(doc)));
		}
		// groups opened together are fitted and synced once, after the last
		if (this.batching) return;
		if (node.children) this.fit_labels();
		this.sync_checks();
	}

	sync_checks() {
		// the list syncs the group boxes too when rows are selected
		if (this.list.checked_docnames.size) this.list.set_rows_as_checked();
		else this.sync_group_checks();
	}

	tail_html(...children) {
		return $(
			'<div class="list-group-message list-group-tail flex items-center gap-2 text-sm text-ink-gray-5"></div>'
		).append(children);
	}

	tail_button(label, onclick) {
		return frappe.ui.button({ label, variant: "ghost", size: "sm", onclick });
	}

	message_html(node) {
		if (!node.failed) return this.tail_html().text(__("No rows in this group"));
		const more = Boolean(node.failed_more);
		return this.tail_html(
			$("<span></span>").text(
				more
					? __("The rest of this group could not be loaded")
					: __("This group could not be loaded")
			),
			this.tail_button(__("Try again"), () => this.load(node, { more }))
		);
	}

	/** Ends a big group on a phone: a tap loads the next page and lets scrolling load up to 100 more. */
	load_more_html(node, loaded) {
		const button = this.tail_button(__("Load More"), () => {
			const had_focus = button[0] === document.activeElement;
			node.auto_load_limit = loaded + AUTO_LOAD_LIMIT;
			this.load(node, { more: true }).then(() => {
				if (had_focus) this.focus_item(node, loaded);
			});
		});
		// rows left is known from the group's count; sub-groups left is not
		const left =
			!this.is_nested(node) &&
			$("<span></span>").text(__("{0} left", [format_number(node.count - loaded, null, 0)]));
		return this.tail_html(button, left || "").addClass("list-group-load-more");
	}

	focus_item(node, index) {
		const item = node.$body.children(":not(.list-group-tail)")[index];
		const row = item?.classList.contains("list-group-section")
			? item.querySelector(":scope > .list-group-row")
			: item;
		row?.focus();
	}

	observe_end(node) {
		const $end = $('<div class="list-group-tail h-px" aria-hidden="true"></div>').appendTo(
			node.$body
		);
		node.end_observer = new IntersectionObserver(
			(entries) => {
				if (!entries.some((entry) => entry.isIntersecting)) return;
				this.stop_end_observer(node);
				this.load(node, { more: true });
			},
			{ root: this.scroll_root(), rootMargin: "0px 0px 200% 0px" }
		);
		node.end_observer.observe($end[0]);
		this.observers.add(node.end_observer);
	}

	stop_end_observer(node) {
		if (!node.end_observer) return;
		node.end_observer.disconnect();
		this.observers.delete(node.end_observer);
		node.end_observer = null;
	}

	load(node, { more = false } = {}) {
		if (node.loading) return Promise.resolve();
		// a group kept from before a refresh loads again from its start
		if (node.stale) more = false;
		const nested = this.is_nested(node);
		const start = more ? node.next_start : 0;
		const step = this.row_step();
		// after a refresh, a group gets back as many rows as it had before
		const page_length = more ? step : Math.max(step, this.loaded_counts.get(node.id) || 0);
		const { figures_token } = this;

		Object.assign(node, { loading: true, loading_more: more, stale: false, failed: false });
		if (more) this.add_to_body(node, []);
		else this.render_body(node);
		const request = nested
			? this.fetch_groups(node, start, page_length)
			: this.fetch_rows(node, start, page_length);

		// a refresh or a new grouping while this loads puts new groups in place of this one
		const current = () => this.nodes.get(node.id) === node && node.$group?.[0].isConnected;
		let added;
		return request
			.then(({ items, has_more }) => {
				if (!current()) return;
				if (nested) {
					// figures asked for another way since: they come again with the next refresh
					if (this.figures_token !== figures_token)
						items.forEach((group) => (group.totals = {}));
					const offset = more ? node.children.length : 0;
					const old = new Map((node.children || []).map((child) => [child.id, child]));
					items = items.map((group, i, all) =>
						this.make_node(group, node, offset + i, more ? null : all)
					);
					if (!more)
						items.forEach((child) => this.keep_loaded(child, old.get(child.id)));
					node.children = more ? node.children.concat(items) : items;
				} else {
					node.rows = more ? node.rows.concat(items) : items;
				}
				node.has_more = has_more;
				node.next_start = start + page_length;
				// the empty sub-group isn't on a page
				const paged = nested ? node.children.filter((c) => c.value !== "") : node.rows;
				this.loaded_counts.set(node.id, paged.length);
				if (more) added = items;
			})
			.catch(() => {
				// frappe.call has shown the error: stop here instead of asking again on scroll
				Object.assign(node, { failed: true, failed_more: more });
			})
			.finally(() => {
				Object.assign(node, { loading: false, loading_more: false });
				if (!current()) return;
				this.sync_data();
				// a record that left the group leaves the selection too
				if (!more) this.list.prune_checked_docnames();
				// closed while it loaded: its rows show the next time it opens, ticked if the group is
				if (!node.open) {
					if (node.selected && node.rows) {
						node.rows.forEach((doc) => this.list.checked_docnames.add(name_of(doc)));
						this.sync_checks();
					}
					return;
				}
				if (added) this.add_to_body(node, added);
				else this.render_body(node);
				this.list.update_checkbox();
			});
	}

	fetch_rows(node, start, page_length) {
		const list = this.list;
		const args = list.get_args();
		Object.assign(args, {
			filters: [...args.filters, ...this.filters_of(node)],
			start,
			page_length,
		});
		return Promise.resolve(frappe.call({ method: list.method, args })).then((r) => {
			const rows = list.rows_of(r.message);
			return { items: rows, has_more: rows.length === page_length };
		});
	}

	fetch_groups(node, start, page_length) {
		const depth = node.depth + 1;
		return Promise.resolve(frappe.call(this.group_request(node, start, page_length))).then(
			async (r) => {
				const page = this.groups_of(r.message, depth, page_length);
				await this.fetch_currencies(
					page.items.filter((group) => this.lacks_currencies(group)),
					node
				);
				const ranked = Boolean(this.rank_of(depth));
				if (this.loads_at_once(this.levels[depth].fieldname)) return page;
				if (page.has_more && !ranked) return page;
				// a ranked empty group comes with the first page and waits for its own page
				const empty =
					ranked && start
						? Promise.resolve(node.empty_group)
						: this.fetch_empty_group(node);
				return empty.then((group) => {
					const index = group
						? this.empty_index(page.items, group, depth, page.has_more)
						: -1;
					node.empty_group = index === -1 ? group : null;
					if (index !== -1) page.items.splice(index, 0, group);
					return page;
				});
			}
		);
	}

	toggle(node, { whole_level = false } = {}) {
		if (whole_level) this.set_level_open(node.depth, !node.open);
		else this.set_open(node, !node.open);
		this.sync_toggle_all();
	}

	set_open(node, open, { remember = true, animate = true } = {}) {
		if (remember) this.open_state.set(node.id, open);
		if (node.open === open) return;
		node.open = open;
		// a group inside a closed one is drawn the next time its parent opens
		if (!node.$group?.[0].isConnected) return;
		node.$group.children(".list-group-row").attr("aria-expanded", open);
		if (open) {
			node.failed = false;
			this.keep_first_page(node);
			this.open_body(node);
		}
		this.slide(node, { animate });
	}

	/** Slides over the part on screen only, so all of the slide is seen. */
	slide(node, { animate = true } = {}) {
		const $collapse = node.$group.children(".list-group-collapse");
		const body = node.$body[0];
		// a slide still running goes on from where it is
		const from = node.slide && body.getBoundingClientRect().height;
		node.slide?.cancel();
		node.slide = null;
		const done = () => {
			$collapse.removeClass("is-animating");
			if (node.open) return;
			this.stop_end_observer(node);
			node.$body.empty();
		};
		if (!node.open && !this.batching) this.unstick(node);
		node.$group.toggleClass("is-open", node.open);
		if (!animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches)
			return done();
		const root = this.scroll_root()?.getBoundingClientRect();
		const bottom = Math.min(window.innerHeight, root?.bottom ?? Infinity);
		const on_screen = Math.max(bottom - body.getBoundingClientRect().top, 0);
		const height = Math.min(body.scrollHeight, on_screen);
		const start = from ?? (node.open ? 0 : height);
		$collapse.addClass("is-animating");
		node.slide = body.animate(
			[{ height: `${start}px` }, { height: node.open ? `${height}px` : "0px" }],
			{ duration: 200, easing: "ease-out" }
		);
		node.slide.finished.then(
			() => {
				node.slide = null;
				done();
			},
			() => {}
		);
	}

	/** A group closed from its header stuck at the top scrolls back, so the header sits in its place. */
	unstick(node) {
		const past = this.stuck_by(node);
		if (past > 1) this.scroll_box().scrollTop -= past;
	}

	stuck_by(node) {
		const row = node.$group.children(".list-group-row")[0];
		return row.getBoundingClientRect().top - node.$group[0].getBoundingClientRect().top;
	}

	/** Opens or closes every group at this depth, also those loaded later. */
	set_level_open(depth, open) {
		this.level_open.set(depth, open);
		const nodes = [...this.nodes.values()].filter((node) => node.depth === depth);
		const shown = (node) => node.open && node.$group?.[0].isConnected;
		const stuck = !open && nodes.find((node) => shown(node) && this.stuck_by(node) > 1);
		const stuck_top =
			stuck && stuck.$group.children(".list-group-row")[0].getBoundingClientRect().top;
		// many groups at once: each group's own layout work would lay the page out once per group
		this.batching = true;
		try {
			for (const node of nodes) {
				this.open_state.delete(node.id);
				this.set_open(node, open, { remember: false, animate: false });
			}
		} finally {
			this.batching = false;
		}
		// the stuck group's header sits where it was, now in its place
		if (stuck) {
			this.scroll_box().scrollTop += stuck.$group[0].getBoundingClientRect().top - stuck_top;
		}
		this.fit_labels();
		this.sync_checks();
	}

	/** Every level is open: its groups loaded so far, and one not loaded yet only if it was opened whole. */
	all_open() {
		const nodes = [...this.nodes.values()];
		return (
			this.groups.length > 0 &&
			this.levels.every((level, depth) => {
				const at_depth = nodes.filter((node) => node.depth === depth);
				return (
					at_depth.every((node) => node.open) &&
					(at_depth.length > 0 || this.level_open.get(depth) === true)
				);
			})
		);
	}

	set_all_open(open) {
		this.levels.forEach((level, depth) => this.set_level_open(depth, open));
		this.sync_toggle_all();
	}

	sync_toggle_all() {
		const open = this.all_open();
		const label = open ? __("Collapse all groups") : __("Expand all groups");
		this.list.$result
			.find(".list-group-toggle-all")
			.attr({ title: label, "aria-label": label, "aria-expanded": open })
			.html(frappe.utils.icon(open ? "chevrons-down" : "chevrons-right", "sm"));
	}

	/** Also ticks the rows the group loads later; a closed group opens to show them. */
	select_group(node, checked) {
		const checked_names = this.list.checked_docnames;
		const mark = (group) => {
			group.selected = checked;
			group.children?.forEach(mark);
		};
		mark(node);
		if (!checked) {
			// other ticked groups keep a record they share with this one; the groups this one is in don't
			const around = new Set(
				node.$group
					.parents(".list-group-section")
					.get()
					.map((section) => section.dataset.groupId)
			);
			this.still_selected = [...this.nodes.values()].filter(
				(other) => other.selected && !around.has(other.id)
			);
		}
		for (const doc of this.rows_under(node)) {
			if (checked) checked_names.add(name_of(doc));
			else checked_names.delete(name_of(doc));
		}
		if (checked && !node.open) this.toggle(node);
	}

	/** The list's selection was cleared: no group ticks the rows it loads later. */
	unselect_all() {
		for (const node of this.nodes.values()) node.selected = false;
	}

	rows_under(node) {
		return node.children
			? node.children.flatMap((child) => this.rows_under(child))
			: node.rows || [];
	}

	/** Ticked when the group, all its loaded rows or all its sub-groups with rows are; half when some rows are. */
	sync_group_checks() {
		const checked_names = this.list.checked_docnames;
		const states = new Map();
		const state_of = (node) => {
			if (states.has(node)) return states.get(node);
			const rows = this.rows_under(node);
			const ticked = rows.filter((doc) => checked_names.has(name_of(doc))).length;
			const some = ticked > 0;
			// a row unticked from elsewhere (Ctrl-click, a drag, the header) takes the group out
			if (node.selected && ticked < rows.length) node.selected = false;
			const with_rows = (node.children || []).filter((child) => child.count);
			const all =
				node.selected ||
				(node.children
					? with_rows.length > 0 && with_rows.every((child) => state_of(child).all)
					: rows.length > 0 && ticked === rows.length);
			const state = { all, some, rows };
			states.set(node, state);
			return state;
		};
		for (const node of this.nodes.values()) {
			const { all, some, rows } = state_of(node);
			if (!node.$group?.[0].isConnected) continue;
			// a closed group's checkbox opens it and selects its rows; a group of groups needs some loaded
			const nested = this.is_nested(node);
			const disabled = !node.count || (nested && !rows.length);
			const label =
				disabled && node.count
					? __("Open a sub-group to select its rows")
					: __("Select the loaded rows of this group");
			// the tip sits on the box's cell: a grey box takes no pointer, its cell does
			node.$group
				.find("> .list-group-row .list-group-checkbox")
				.prop({ checked: all, indeterminate: !all && some, disabled })
				.attr("aria-label", label)
				.parent()
				.attr("title", label);
		}
	}

	/** Each level's headers stick under the one above, and rows focused from the keyboard stay below them. */
	set_sticky_tops() {
		const result = this.list.$result[0];
		const box = result.parentElement;
		// a phone scrolls the page, whose head stays on top of the list's header
		const head = frappe.is_mobile()
			? this.list.page.page_head?.[0]
			: result.querySelector(":scope > .list-row-container");
		const row = result.querySelector(".list-group-row");
		box.style.setProperty("--list-group-top", `${head?.offsetHeight || 0}px`);
		box.style.setProperty("--list-group-row-height", `${row?.offsetHeight || 0}px`);
		// headers below the third level scroll away (list.scss)
		box.style.setProperty("--list-group-levels", Math.min(this.levels.length, 3));
	}

	count_text() {
		if (!this.groups.length && this.empty_pending) return "";
		const count = format_number(this.groups.length, null, 0);
		if (this.has_more) return __("{0}+ groups", [count]);
		return this.groups.length === 1 ? __("1 group") : __("{0} groups", [count]);
	}
}
