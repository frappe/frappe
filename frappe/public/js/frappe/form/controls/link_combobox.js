// Link field using frappe.ui.Combobox, used when the System Settings toggle is on.
// Supports the same hooks as the classic Link field (set_query, get_query, link_options...).
// Extra hook: field.map_options(rows, { query, start }) or df.map_options
// to change, remove or group ([{ group, options }]) rows before they show.

import { describe_link_filters } from "./link_filter_description.js";
import { mount_combobox, awesomplete_shim } from "./combobox_control.js";
import { is_thenable } from "../../ui/components/utils.js";

frappe.ui.form.is_combobox_link_enabled = function () {
	// before boot there are no settings, so use the classic field
	if (!frappe.ui.Combobox || !frappe.sys_defaults) return false;
	return frappe.defaults.is_enabled("enable_combobox_link_field");
};

// Select mode loads up to this many rows; more than that uses Search
const PRELOAD_LIMIT = 1000;

// small cache: drops the oldest entry when full
// search filters in the format get_list accepts
function stamp_filters(filters) {
	if (!filters || Array.isArray(filters)) return filters || {};
	// search option, not a column
	const { include_disabled, ...rest } = filters;
	return rest;
}

// true if both lists have the same rows in the same order
function same_values(a, b) {
	return (
		a.length === b.length &&
		a.every((o, i) => {
			const p = b[i];
			return o.value === p.value && o.label === p.label && o.image === p.image;
		})
	);
}

function remember(map, key, value, max) {
	if (map.has(key)) map.delete(key);
	else if (map.size >= max) map.delete(map.keys().next().value);
	map.set(key, value);
}

// kept short so new records show up soon
const search_cache = new Map(); // key -> { result, time }
const SEARCH_CACHE_MS = 60 * 1000;
const SEARCH_CACHE_MAX = 200;

// checked on every open, as realtime updates can be missed
const preload_cache = new Map(); // key -> { options, stamp } or a pending Promise
const PRELOAD_CACHE_MAX = 20;
const PRELOAD_FRESH_MS = 5 * 1000;
// reload after this long anyway, as a rename doesn't change the stamp
const PRELOAD_STALE_MS = 5 * 60 * 1000;
const preload_fallback = new Set(); // keys whose list exceeded PRELOAD_LIMIT
const no_stamp = new Set(); // keys whose stamp request the server refused

// fields asking for the same image share one request
const image_promises = new Map();
const IMAGE_CACHE_MAX = 500;

// all request args, including get_query ones
function cache_key(args, extra = []) {
	const entries = Object.keys(args)
		.sort()
		.map((k) => [
			k,
			k === "filters" && typeof args[k] !== "string" ? JSON.stringify(args[k]) : args[k],
		]);
	return JSON.stringify([entries, ...extra]);
}

frappe.ui.form.ControlLinkCombobox = class ControlLinkCombobox extends frappe.ui.form.ControlLink {
	make_input() {
		if (this.$input) return;
		this.title_value_map = this.title_value_map || {};

		const combobox = new frappe.ui.Combobox({
			value_input: true,
			open_on_focus: true,
			// in a grid, arrow keys move between rows
			arrow_keys_open: !this.grid_row,
			// no chevron in Search mode, so the value gets more space
			chevron: this.display_mode() === "Select",
			filterable: false, // search_link does the filtering
			// × button follows the "Allow Clearing Link Fields" setting
			clear_button: this.is_clear_button_enabled(),
			options: (query, { start }) => this.fetch_options(query, start),
			filters: () => this.get_filter_chips(),
			actions: [
				{
					icon: "arrow-right",
					title: __("Open Link") + " (Ctrl+Enter)",
					href: "#",
					css_class: "btn-open",
					shortcut: "ctrl+enter",
				},
			],
			before_open: () => this.before_open(),
			// grid_row.js checks this to leave arrow keys to the dropdown
			on_open: () => (this.autocomplete_open = true),
			on_close: (reason) => this.on_close(reason),
			on_change: (value, option) => this.on_pick(value, option),
		});

		mount_combobox(this, combobox);
		this.$input.attr("data-target", this.df.options);

		// for code that uses the classic link button
		this.$link_open = $(combobox.action_els[0]);
		this.setup_buttons();
		this.update_open_link();
	}

	// ---- classic-control surface ----

	get awesomplete() {
		return (this._awesomplete_shim ||= awesomplete_shim(this));
	}

	setup_buttons() {
		if (this.only_input && !this.with_link_btn) {
			this.$link_open.remove();
		}
	}

	// null if the doctype isn't known yet
	get_link_doctype() {
		try {
			return this.get_options() || null;
		} catch (e) {
			return null;
		}
	}

	set_formatted_input(value) {
		this.displayed_value = value || null;
		if (!value) {
			this.show_selected(null, "");
			return;
		}
		// show the name until the title is loaded
		if (this.is_title_link() && !frappe.utils.get_link_title(this.get_link_doctype(), value)) {
			this.show_selected(value, value);
		}
		this.set_link_title(value);
	}

	// called after the title loads; skip if the value changed
	translate_and_set_input_value(link_title, value) {
		if (value !== this.displayed_value) return;
		const text = this.get_translated(link_title || value);
		// can run before make_input (hidden field set by script)
		this.title_value_map = this.title_value_map || {};
		this.title_value_map[text] = value;
		this.show_selected(value, text);
	}

	// the value is in the combobox; the input only shows it
	get_input_value() {
		if (!this.combobox) return super.get_input_value();
		// typed text still being checked counts as the value, like the classic field
		if (this.pending_text != null) return this.pending_text;
		const value = this.combobox.get_value();
		return value == null ? "" : value;
	}

	set_input_value(text) {
		if (!text) return;
		this.show_selected(this.title_value_map[text] || text, text);
	}

	// typed text, used by quick entry to fill the name
	get_label_value() {
		if (this.combobox && this.combobox.is_open) return this.combobox.query || "";
		return this.$input ? this.$input.val() : "";
	}

	// the combobox shows its buttons on hover and focus
	show_link_and_clear_buttons() {
		this.update_open_link();
	}

	hide_link_and_clear_buttons() {}

	toggle_href(doctype) {
		this.update_open_link(doctype);
	}

	refresh_input() {
		super.refresh_input();
		if (this.combobox && this.$input) {
			this.combobox.set_disabled(this.$input.prop("disabled"));
			// a Dynamic Link's doctype can change
			this.combobox.set_chevron(this.display_mode() === "Select");
		}
	}

	// ---- display ----

	show_selected(value, text) {
		if (!this.combobox) return;
		// ignore the old value coming back during a clear; a new value cancels the clear
		if (this.combobox.pending_clear && value === this.combobox.cleared_value) return;
		const avatar = this.show_image();
		const label = text || (value == null ? undefined : String(value));
		this.combobox.set_value(value, { label, avatar });
		this.update_open_link();
		if (value && avatar) {
			// skip if a newer call already ran
			const shown = (this.shown = {});
			this.get_image(value).then((image) => {
				if (!image || this.shown !== shown || this.combobox.get_value() !== value) return;
				this.combobox.set_value(value, { label, image, avatar });
			});
		}
	}

	update_open_link(doctype = this.get_link_doctype()) {
		if (!this.$link_open || !this.$link_open.length) return;
		const name = this.get_input_value();
		const can_open =
			!!name &&
			!!doctype &&
			!(frappe.model.can_select(doctype) && !frappe.model.can_read(doctype));
		this.$link_open[0].hidden = !can_open;
		if (can_open) {
			this.$link_open.attr("href", frappe.utils.get_form_link(doctype, name));
		}
	}

	link_settings() {
		return (frappe.boot.link_settings || {})[this.get_link_doctype()] || {};
	}

	// boot has image fields only for DocTypes that show images
	show_image() {
		return !!this.link_settings().image_field;
	}

	// field name comes from boot, so no meta load needed
	get_image(name) {
		const doctype = this.get_link_doctype();
		const key = `${doctype}::${name}`;
		if (!image_promises.has(key)) {
			remember(image_promises, key, this.load_image(doctype, name), IMAGE_CACHE_MAX);
		}
		return image_promises.get(key);
	}

	load_image(doctype, name) {
		const image_field = this.link_settings().image_field;
		if (!doctype || !image_field) return Promise.resolve(null);
		// user images are already in boot
		if (doctype === "User" && frappe.user_info(name).image) {
			return Promise.resolve(frappe.user_info(name).image);
		}
		// get_value needs read permission; avoid an error dialog
		if (!frappe.model.can_read(doctype)) return Promise.resolve(null);
		return frappe.db
			.get_value(doctype, name, image_field)
			.then((r) => (r.message || {})[image_field] || null)
			.catch(() => null);
	}

	// ---- panel content ----

	// Search loads pages from the server; Select loads the whole list
	display_mode() {
		return this.link_settings().display_mode || "Search";
	}

	// get once per open so rows and chips use the same filters
	before_open() {
		// no try/catch: a Single doctype should show "not a valid DocType"
		this.open_args = this.get_search_args("") || null;
		this.open_mode = this.resolve_mode();
		const searching = this.open_mode === "Search";
		const opts = this.combobox.opts;
		opts.search_placeholder = __("Search {0}...", [__(this.open_args?.doctype || "")]);
		opts.footer = this.get_footer_rows();
		// Select: no search box; typing still jumps to a row
		opts.hide_search = !searching;
		opts.page_size = searching && this.open_args ? this.open_args.page_length : null;
	}

	// Select, unless set to Search or the list is too long
	resolve_mode() {
		if (this.display_mode() === "Search" || !this.open_args) return "Search";
		// a custom query limits its results, so use Search
		if (this.open_args.query) return "Search";
		return preload_fallback.has(cache_key(this.open_args)) ? "Search" : "Select";
	}

	fetch_options(query, start = 0) {
		if (!this.open_args) return [];
		let result;
		if (this.open_mode !== "Search") {
			result = this.preload_options();
		} else {
			// keep later pages in the same order so rows don't jump while scrolling
			const args = { ...this.open_args, txt: query };
			if (start) {
				args.start = start;
				args.keep_order = 1;
			}
			result = this.search(args, { use_get: !query, paged: true });
		}
		return this.apply_map(result, { query, start });
	}

	// run map_options on rows or a { rows, has_more } page; stays sync if possible
	apply_map(result, context) {
		const hook = this.map_options || this.df.map_options;
		if (!hook) return result;
		const map = (r) => {
			const paged = r && !Array.isArray(r) && "rows" in r;
			const wrap = (rows) => (paged ? { ...r, rows } : rows);
			// pass copies, as rows may be cached
			const rows = (paged ? r.rows : r).map((row) => ({ ...row }));
			const mapped = hook.call(this, rows, context);
			return is_thenable(mapped)
				? mapped.then((m) => wrap(m || rows))
				: wrap(mapped || rows);
		};
		return is_thenable(result) ? result.then(map) : map(result);
	}

	// `paged` returns { rows, has_more } for loading more
	search(args, { use_get, no_cache, paged } = {}) {
		// get the doctype for each request (Dynamic Link can change)
		const context = {
			doctype: args.doctype,
			show_image: this.show_image(),
			is_title_link: this.is_title_link(),
		};
		if (context.show_image) args.include_image = 1;

		// skip caches once after creating a record so it shows up
		const created_new = !!this.$input._created_new_doc;
		use_get = use_get && !created_new;
		if (use_get) {
			const [too_large, filters_str] = this.are_filters_large(args.filters);
			use_get = !too_large;
			args.filters = filters_str;
		}

		const key = cache_key(args, [args.txt, args.start || 0, args.page_length]);
		const cached = created_new || no_cache ? null : search_cache.get(key);
		if (cached && Date.now() - cached.time < SEARCH_CACHE_MS) {
			return cached.result;
		}

		return frappe
			.xcall("frappe.desk.search.search_link", args, use_get ? "GET" : "POST", {
				cache: use_get,
				no_spinner: true,
			})
			.then((rows) => {
				this.$input._created_new_doc = false;
				rows = rows || [];
				// a full page may have more rows
				const more = !!args.page_length && rows.length >= args.page_length;
				rows = this.merge_duplicates(rows);
				for (const row of rows) {
					// don't cache a name as the title
					if (row.label && row.label !== row.value) {
						frappe.utils.add_link_title(context.doctype, row.value, row.label);
					}
				}
				const options = rows.map((row) => this.to_option(row, context));
				// count before removing duplicates
				const result = paged ? { rows: options, has_more: more } : options;
				if (!no_cache) {
					remember(search_cache, key, { result, time: Date.now() }, SEARCH_CACHE_MAX);
				}
				return result;
			});
	}

	// Select: load the whole list, reload only if records changed
	preload_options() {
		const key = cache_key(this.open_args);
		const cached = this.$input._created_new_doc ? null : preload_cache.get(key);
		// reuse a request already running
		if (cached && typeof cached.then === "function") return cached;
		// use a fresh list as is; show an older one and check it in the background
		if (cached && Date.now() - cached.time < PRELOAD_FRESH_MS) return cached.options;

		// copy args, as another open may change open_args
		const open_args = this.open_args;
		// reuse a reload already running
		const pending =
			cached?.pending ||
			this.rebuild_preload(key, cached, open_args)
				.catch((error) => {
					// don't cache a failed request
					if (!cached) preload_cache.delete(key);
					throw error;
				})
				.finally(() => {
					if (cached) cached.pending = null;
				});
		if (!cached) {
			remember(preload_cache, key, pending, PRELOAD_CACHE_MAX);
			return pending;
		}
		cached.pending = pending;
		// show cached list now; refresh if it changed and the user hasn't moved yet
		pending
			.then((options) => {
				const cb = this.combobox;
				if (options === cached.options || !cb.is_open || this.open_args !== open_args)
					return;
				if (!cb.navigated && !cb.typeahead_buffer) cb.load();
			})
			.catch(() => {});
		return cached.options;
	}

	// use the cached list if records haven't changed, else load again
	async rebuild_preload(key, cached, open_args) {
		const stamp = await this.preload_stamp(open_args);
		if (
			cached &&
			stamp &&
			cached.stamp === stamp &&
			Date.now() - cached.time < PRELOAD_STALE_MS
		) {
			return cached.options;
		}
		const args = { ...open_args, txt: "", page_length: PRELOAD_LIMIT + 1 };
		// has_more uses the count before removing duplicates
		const page = await this.search(args, { use_get: false, no_cache: true, paged: true });
		let options = page.rows;
		if (page.has_more) {
			this.fall_back_to_search(key, open_args);
			return options.slice(0, PRELOAD_LIMIT);
		}
		// can't check changes: keep the cached list if rows are the same
		if (cached && !stamp && same_values(options, cached.options)) options = cached.options;
		remember(preload_cache, key, { options, stamp, time: Date.now() }, PRELOAD_CACHE_MAX);
		return options;
	}

	// list too long: switch to Search
	fall_back_to_search(key, open_args) {
		console.warn(
			`Link field: ${open_args.doctype} has more than ${PRELOAD_LIMIT} records, ` +
				`falling back to Search mode (set its Link Display Mode to Search)`
		);
		preload_fallback.add(key);
		preload_cache.delete(key);
		// reopen the panel in Search mode
		const cb = this.combobox;
		if (cb.is_open && this.open_args === open_args && !cb.navigated && !cb.typeahead_buffer) {
			// keep a pending clear for the reopened panel
			const clearing = cb.pending_clear;
			cb.pending_clear = false;
			cb.close("owner");
			cb.open({ motion: "instant" });
			cb.pending_clear = clearing;
			// panel didn't reopen: finish the clear
			if (!cb.is_open) cb.flush_clear();
		}
	}

	// record count and last modified time, or null if not readable
	preload_stamp(open_args) {
		const { doctype, filters, query, ignore_user_permissions } = open_args;
		// can't check changes when search and list may return different rows
		if (
			query ||
			ignore_user_permissions ||
			doctype === "DocType" ||
			!(frappe.model.can_read(doctype) || frappe.model.can_select(doctype)) ||
			frappe.defaults.get_user_permissions()?.[doctype]
		) {
			return Promise.resolve(null);
		}
		// don't ask again if the server refused it before
		const key = cache_key(open_args);
		if (no_stamp.has(key)) return Promise.resolve(null);
		// plain request so errors don't show dialogs
		const call = (method, body) =>
			fetch(`/api/method/${method}`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Accept: "application/json",
					"X-Frappe-CSRF-Token": frappe.csrf_token,
				},
				body: JSON.stringify(body),
			})
				.then((res) => {
					if (!res.ok) throw new Error(res.statusText);
					return res.json();
				})
				.then((r) => r.message);
		const stamp_filters_value = stamp_filters(filters);
		// count shows deletes, max modified shows edits and inserts
		return Promise.all([
			call("frappe.client.get_count", { doctype, filters: stamp_filters_value }),
			call("frappe.client.get_list", {
				doctype,
				filters: stamp_filters_value,
				fields: [{ MAX: "modified", as: "m" }],
				limit_page_length: 1,
			}),
		])
			.then(([n, rows]) => {
				const m = rows && rows[0] && rows[0].m;
				return n != null && m !== undefined ? JSON.stringify({ n, m }) : null;
			})
			.catch(() => {
				no_stamp.add(key);
				return null;
			});
	}

	to_option(row, { doctype, show_image, is_title_link }) {
		const label = this.get_translated(row.label || row.value);
		let description = row.description;
		// show the name only when it differs from the label
		if (description && !is_title_link && description === row.value) {
			description = null;
		}
		if (description) description = __(frappe.utils.html2text(description));
		if (show_image) {
			// image is in the result, so no extra request
			const key = `${doctype}::${row.value}`;
			remember(image_promises, key, Promise.resolve(row.image || null), IMAGE_CACHE_MAX);
		}
		return { label, value: row.value, description, image: row.image, avatar: show_image };
	}

	async get_filter_chips() {
		if (this.df.filter_description) {
			// may contain HTML; chips show plain text
			return frappe.utils.html2text(String(this.df.filter_description));
		}
		const filters = this.open_args && this.open_args.filters;
		const empty =
			!filters || (Array.isArray(filters) ? !filters.length : !Object.keys(filters).length);
		if (empty) return [];
		const descriptions = await describe_link_filters(this.get_link_doctype(), filters);
		// formatter may return HTML; chips show plain text
		return descriptions.map((text) => frappe.utils.html2text(text));
	}

	get_footer_rows() {
		const doctype = this.get_link_doctype();
		const rows = [];
		if (!doctype || this.df.only_select) return rows;

		if (frappe.model.can_create(doctype)) {
			rows.push({
				type: "custom",
				icon: "plus",
				label: __("Create a new {0}", [__(doctype)]),
				onclick: () => this.new_doc(),
			});
		}

		// link actions registered by apps
		const custom = frappe.ui.form.ControlLink.link_options
			? frappe.ui.form.ControlLink.link_options(this)
			: null;
		for (const item of custom || []) {
			const label = item.label || frappe.utils.html2text(item.html || "");
			rows.push({
				type: "custom",
				label,
				// an entry without action is a value, like the classic field
				onclick: () => {
					if (item.action) return item.action.apply(this);
					this.combobox.set_value(item.value, { label });
					this.on_pick(item.value, { label, value: item.value });
				},
			});
		}

		// no Advanced Search: the panel loads more on scroll
		return rows;
	}

	// ---- picking ----

	// stop checking typed text from a close and release the held clear
	drop_lookup() {
		this.lookup = null;
		this.pending_text = null;
		this.combobox.release_clear();
	}

	// promise for the value being set, so Ctrl+S can wait
	parse_validate_and_set_in_model(value, e) {
		return (this.last_write = super.parse_validate_and_set_in_model(value, e));
	}

	on_pick(value, option) {
		// a pick cancels the typed text check
		this.drop_lookup();
		if (value == null) {
			// a clear goes through the normal change flow
			this.$input.trigger("change");
			this.update_open_link();
			return this.last_write;
		}
		if (this.df.remember_last_selected_value) {
			frappe.boot.user.last_selected_values[this.df.options] = value;
		}
		this.title_value_map[option.label] = value;
		this.label = this.get_translated(option.label);
		// cache only a real title, not free text
		if (option.label && option.label !== value) {
			frappe.utils.add_link_title(this.get_link_doctype(), value, option.label);
		}
		// set the value, then trigger change for dialogs and MultiSelectDialog
		this.$input.trigger("change");
		this.$input.trigger("awesomplete-selectcomplete");
		return this.last_write;
	}

	// on click away or Tab, typed text picks the matching row; else it is dropped
	on_close(reason) {
		this.autocomplete_open = false;
		const query = this.combobox.query;
		// a pick cancels the typed text check
		if (reason === "select") this.drop_lookup();
		// Escape, disabled or hidden drop the text; other closes save it
		if (!query || ["escape", "select", "disabled", "hidden"].includes(reason)) return;
		// cancel the check started by an earlier close
		this.drop_lookup();
		const value_at_close = this.combobox.get_value() ?? "";
		if (this.df.ignore_link_validation) {
			// any text is allowed here, but a matching row is still picked
			this.combobox.pending_clear = false;
			const row = this.combobox.match_option(query);
			const title_value = this.title_value_map?.[query];
			const value = row ? row.value : title_value || query;
			if (value !== value_at_close) {
				const option = row || { label: query, value };
				this.combobox.set_value(value, { label: option.label, image: option.image });
				this.on_pick(value, option);
			}
			return;
		}
		const commit = (match) => {
			if (!match) return;
			// any pick ends the clear
			this.combobox.pending_clear = false;
			if (match.value === value_at_close) return;
			this.combobox.set_value(match.value, { label: match.label, image: match.image });
			return this.on_pick(match.value, match);
		};
		const match = this.combobox.match_option(query);
		if (match || !this.combobox.rows_pending) return commit(match);
		// rows not loaded yet (paste + Tab): look the text up, keep the clear waiting
		const cb = this.combobox;
		cb.hold_clear();
		this.pending_text = query;
		// a later close starts its own check
		const lookup = (this.lookup = {});
		const current = () => cb.get_value() ?? "";
		const settle = (found) => {
			// outdated: don't let a waiting save run
			if (this.lookup !== lookup) return false;
			this.pending_text = null;
			cb.release_clear();
			if (found) return commit(found);
			// reopened: the next close finishes the clear
			if (!cb.is_open) cb.flush_clear();
		};
		// errors from the hook still finish
		return new Promise((resolve) => resolve(this.fetch_options(query)))
			.then((r) => {
				// the field changed or was removed
				if (current() !== value_at_close || !document.body.contains(this.$input[0])) {
					return settle(null);
				}
				return settle(frappe.ui.Combobox.match_in(Array.isArray(r) ? r : r.rows, query));
			})
			.catch(() => settle(null));
	}
};
