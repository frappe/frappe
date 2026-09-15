// Link field backed by frappe.ui.Combobox.
// Picked by make_control for Link fields when "Enable Combobox Link and
// Autocomplete Fields" is on in System Settings.
//
// Extension points, same as the classic control plus one:
//   frm.set_query / df.get_query      filters, or a custom server `query` method
//   df.change, fetch_from, df.only_select, df.filter_description, link_options
//   field.map_options(rows, { query, start })  rows before they show: re-rank,
//     drop, or return groups ([{ group, options }]); for later pages return
//     rows under the same group so they continue it. Also as df.map_options.

import { describe_link_filters } from "./link_filter_description.js";
import { mount_combobox, awesomplete_shim } from "./combobox_control.js";
import { is_thenable } from "../../ui/components/utils.js";

frappe.ui.form.is_combobox_link_enabled = function () {
	// desk only; a control made before boot has no setting, so it stays classic
	if (!frappe.ui.Combobox || !frappe.sys_defaults) return false;
	return frappe.defaults.is_enabled("enable_combobox_link_field");
};

// Select mode preloads at most this many rows; longer lists fall back to Search
const PRELOAD_LIMIT = 1000;

// bounded caches: oldest entry evicted first, an overwrite counts as newest
// the search's filters as a plain list query takes them
function stamp_filters(filters) {
	if (!filters || Array.isArray(filters)) return filters || {};
	// search_widget's own switch, not a column
	const { include_disabled, ...rest } = filters;
	return rest;
}

// two option lists showing the same rows in the same order
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

// short life so new records don't stay hidden
const search_cache = new Map(); // key -> { result, time }
const SEARCH_CACHE_MS = 60 * 1000;
const SEARCH_CACHE_MAX = 200;

// stamp is rechecked on every open: list views drop push listeners on refresh
const preload_cache = new Map(); // key -> { options, stamp } or a pending Promise
const PRELOAD_CACHE_MAX = 20;
const PRELOAD_FRESH_MS = 5 * 1000;
// a stamp can't see a rename: the list is rebuilt anyway after this long
const PRELOAD_STALE_MS = 5 * 60 * 1000;
const preload_fallback = new Set(); // keys whose list exceeded PRELOAD_LIMIT
const no_stamp = new Set(); // keys whose stamp request the server refused

// one promise per doctype + name so concurrent fields share a request
const image_promises = new Map();
const IMAGE_CACHE_MAX = 500;

// every argument the server sees (a get_query may add its own keys)
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
			// in a grid row the arrow keys move between rows
			arrow_keys_open: !this.grid_row,
			// no chevron while searching: the value gets the whole width
			chevron: this.display_mode() === "Select",
			filterable: false, // search_link does the filtering
			// the × follows the "Allow Clearing Link Fields" setting; keys still clear
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
			// grid_row.js reads this flag to leave arrow keys to the dropdown
			on_open: () => (this.autocomplete_open = true),
			on_close: (reason) => this.on_close(reason),
			on_change: (value, option) => this.on_pick(value, option),
		});

		mount_combobox(this, combobox);
		this.$input.attr("data-target", this.df.options);

		// for code that toggles the classic "open link" handle
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

	// null while the target can't be resolved; display code must not throw
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
		// a title still to be fetched: the name now, the title when it lands
		if (this.is_title_link() && !frappe.utils.get_link_title(this.get_link_doctype(), value)) {
			this.show_selected(value, value);
		}
		this.set_link_title(value);
	}

	// set_link_title lands here, maybe after a fetch: only for the value still shown
	translate_and_set_input_value(link_title, value) {
		if (value !== this.displayed_value) return;
		const text = this.get_translated(link_title || value);
		// reachable before make_input (a hidden field set from a script)
		this.title_value_map = this.title_value_map || {};
		this.title_value_map[text] = value;
		this.show_selected(value, text);
	}

	// the widget holds the value; the input text is only what it shows
	get_input_value() {
		if (!this.combobox) return super.get_input_value();
		// text still being looked up after a close reads as the value, as it did
		// in the classic input
		if (this.pending_text != null) return this.pending_text;
		const value = this.combobox.get_value();
		return value == null ? "" : value;
	}

	set_input_value(text) {
		if (!text) return;
		this.show_selected(this.title_value_map[text] || text, text);
	}

	// the typed query while open: quick entry pre-fills the name with it
	get_label_value() {
		if (this.combobox && this.combobox.is_open) return this.combobox.query || "";
		return this.$input ? this.$input.val() : "";
	}

	// the widget shows its buttons on hover / focus by itself
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
			// a Dynamic Link's target (and so its mode) can change with the doc
			this.combobox.set_chevron(this.display_mode() === "Select");
		}
	}

	// ---- display ----

	show_selected(value, text) {
		if (!this.combobox) return;
		// the value being cleared echoing back (a pick still validating) is dropped;
		// a different value replaces the clear
		if (this.combobox.pending_clear && value === this.combobox.cleared_value) return;
		const avatar = this.show_image();
		const label = text || (value == null ? undefined : String(value));
		this.combobox.set_value(value, { label, avatar });
		this.update_open_link();
		if (value && avatar) {
			// a later show (the title arriving) outranks this one's image callback
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

	// boot names the image field only for DocTypes that show images in links
	show_image() {
		return !!this.link_settings().image_field;
	}

	// boot names the field, so the target meta needn't be loaded here
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
		// users already in boot carry their image
		if (doctype === "User" && frappe.user_info(name).image) {
			return Promise.resolve(frappe.user_info(name).image);
		}
		// get_value needs read permission; avoid a "not permitted" dialog
		if (!frappe.model.can_read(doctype)) return Promise.resolve(null);
		return frappe.db
			.get_value(doctype, name, image_field)
			.then((r) => (r.message || {})[image_field] || null)
			.catch(() => null);
	}

	// ---- panel content ----

	// Search pages from the server; Select preloads the whole list
	display_mode() {
		return this.link_settings().display_mode || "Search";
	}

	// computed once per open: rows and chips must see the same get_query state
	before_open() {
		// unguarded on purpose: a Single target should raise "not a valid DocType"
		this.open_args = this.get_search_args("") || null;
		this.open_mode = this.resolve_mode();
		const searching = this.open_mode === "Search";
		const opts = this.combobox.opts;
		opts.search_placeholder = __("Search {0}...", [__(this.open_args?.doctype || "")]);
		opts.footer = this.get_footer_rows();
		// Select: no search box; type-to-jump still works
		opts.hide_search = !searching;
		opts.page_size = searching && this.open_args ? this.open_args.page_length : null;
	}

	// Select unless the setting says Search or the list proved too long
	resolve_mode() {
		if (this.display_mode() === "Search" || !this.open_args) return "Search";
		// a custom query caps its own page: only a search can reach every row
		if (this.open_args.query) return "Search";
		return preload_fallback.has(cache_key(this.open_args)) ? "Search" : "Select";
	}

	fetch_options(query, start = 0) {
		if (!this.open_args) return [];
		let result;
		if (this.open_mode !== "Search") {
			result = this.preload_options();
		} else {
			// the server ranks the first page; later pages keep database order so
			// scrolling doesn't reshuffle rows already seen
			const args = { ...this.open_args, txt: query };
			if (start) {
				args.start = start;
				args.keep_order = 1;
			}
			result = this.search(args, { use_get: !query, paged: true });
		}
		return this.apply_map(result, { query, start });
	}

	// the field's map_options hook, on plain rows or a { rows, has_more } page;
	// a synchronous result stays synchronous (a cached list renders at once)
	apply_map(result, context) {
		const hook = this.map_options || this.df.map_options;
		if (!hook) return result;
		const map = (r) => {
			const paged = r && !Array.isArray(r) && "rows" in r;
			const wrap = (rows) => (paged ? { ...r, rows } : rows);
			// the hook gets copies: the list and its rows may be cached and shared
			const rows = (paged ? r.rows : r).map((row) => ({ ...row }));
			const mapped = hook.call(this, rows, context);
			return is_thenable(mapped)
				? mapped.then((m) => wrap(m || rows))
				: wrap(mapped || rows);
		};
		return is_thenable(result) ? result.then(map) : map(result);
	}

	// `paged` answers { rows, has_more } so the combobox can fetch more
	search(args, { use_get, no_cache, paged } = {}) {
		// resolved once per request: a Dynamic Link resolves its target each time
		const context = {
			doctype: args.doctype,
			show_image: this.show_image(),
			is_title_link: this.is_title_link(),
		};
		if (context.show_image) args.include_image = 1;

		// GET is browser-cacheable; a field that just created a record skips every
		// cache once so the new record shows up
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
				// a full page may have more (an exactly full last page costs one
				// empty request); merged duplicates must not make it look short
				const more = !!args.page_length && rows.length >= args.page_length;
				rows = this.merge_duplicates(rows);
				for (const row of rows) {
					// a bare name must not pre-empt the title fetch for title links
					if (row.label && row.label !== row.value) {
						frappe.utils.add_link_title(context.doctype, row.value, row.label);
					}
				}
				const options = rows.map((row) => this.to_option(row, context));
				// use the raw count: merging duplicates can leave a full page short
				const result = paged ? { rows: options, has_more: more } : options;
				if (!no_cache) {
					remember(search_cache, key, { result, time: Date.now() }, SEARCH_CACHE_MAX);
				}
				return result;
			});
	}

	// Select: the whole list, rebuilt only when the stamp changed
	preload_options() {
		const key = cache_key(this.open_args);
		const cached = this.$input._created_new_doc ? null : preload_cache.get(key);
		// a fetch already under way: share it
		if (cached && typeof cached.then === "function") return cached;
		// a list fetched moments ago (tabbing down a column) is served as is;
		// older ones show at once and are revalidated in the background below
		if (cached && Date.now() - cached.time < PRELOAD_FRESH_MS) return cached.options;

		// this open's arguments: another open may replace open_args meanwhile
		const open_args = this.open_args;
		// a rebuild already under way for a stale list is shared too
		const pending =
			cached?.pending ||
			this.rebuild_preload(key, cached, open_args)
				.catch((error) => {
					// a failed fetch must not be served again; a good cached list stays
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
		// show the cached list now; reload the open panel if the rebuild differs
		// and the user hasn't started moving through it
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

	// the cached list when the records' stamp still matches, else a fresh one
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
		// paged: has_more counts the rows before duplicates were merged
		const page = await this.search(args, { use_get: false, no_cache: true, paged: true });
		let options = page.rows;
		if (page.has_more) {
			this.fall_back_to_search(key, open_args);
			return options.slice(0, PRELOAD_LIMIT);
		}
		// no stamp to compare: keep the cached array when the list is the same
		if (cached && !stamp && same_values(options, cached.options)) options = cached.options;
		remember(preload_cache, key, { options, stamp, time: Date.now() }, PRELOAD_CACHE_MAX);
		return options;
	}

	// too long for the client: search the server from now on, this open included
	fall_back_to_search(key, open_args) {
		console.warn(
			`Link field: ${open_args.doctype} has more than ${PRELOAD_LIMIT} records, ` +
				`falling back to Search mode (set its Link Display Mode to Search)`
		);
		preload_fallback.add(key);
		preload_cache.delete(key);
		// the panel still showing this list reopens as a search
		const cb = this.combobox;
		if (cb.is_open && this.open_args === open_args && !cb.navigated && !cb.typeahead_buffer) {
			// a clear waiting on a pick carries over to the reopened panel
			const clearing = cb.pending_clear;
			cb.pending_clear = false;
			cb.close("owner");
			cb.open({ motion: "instant" });
			cb.pending_clear = clearing;
			// nothing reopened (the field went away): the clear settles now
			if (!cb.is_open) cb.flush_clear();
		}
	}

	// count + latest change of the records, or null when it can't be read
	// (select-only permission, a virtual doctype); silent: no error dialog
	preload_stamp(open_args) {
		const { doctype, filters, query, ignore_user_permissions } = open_args;
		// no stamp can vouch for the list when the search sees other rows than a
		// plain list does: a custom query, permissions ignored or restricted
		if (
			query ||
			ignore_user_permissions ||
			doctype === "DocType" ||
			!(frappe.model.can_read(doctype) || frappe.model.can_select(doctype)) ||
			frappe.defaults.get_user_permissions()?.[doctype]
		) {
			return Promise.resolve(null);
		}
		// a refused stamp (a server-side custom query's own filter keys) isn't asked again
		const key = cache_key(open_args);
		if (no_stamp.has(key)) return Promise.resolve(null);
		// a plain request: a refusal here must not raise the desk's error dialogs
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
		// the count catches deletes, the latest modified catches edits and
		// inserts; one aggregate per query keeps the list query's ordering out
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
		// a docname under an identical label says nothing; title links need it
		if (description && !is_title_link && description === row.value) {
			description = null;
		}
		if (description) description = __(frappe.utils.html2text(description));
		if (show_image) {
			// the result carries the image: no by-name fetch needed later
			const key = `${doctype}::${row.value}`;
			remember(image_promises, key, Promise.resolve(row.image || null), IMAGE_CACHE_MAX);
		}
		return { label, value: row.value, description, image: row.image, avatar: show_image };
	}

	async get_filter_chips() {
		if (this.df.filter_description) {
			// app-supplied, may carry markup; chips are text
			return frappe.utils.html2text(String(this.df.filter_description));
		}
		const filters = this.open_args && this.open_args.filters;
		const empty =
			!filters || (Array.isArray(filters) ? !filters.length : !Object.keys(filters).length);
		if (empty) return [];
		const descriptions = await describe_link_filters(this.get_link_doctype(), filters);
		// a formatter may still return markup; chips are text
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
				// an entry without an action is a value to pick, as in the classic control
				onclick: () => {
					if (item.action) return item.action.apply(this);
					this.combobox.set_value(item.value, { label });
					this.on_pick(item.value, { label, value: item.value });
				},
			});
		}

		// no Advanced Search row: the panel pages on scroll itself
		return rows;
	}

	// ---- picking ----

	// a lookup started at a close: the text reads as the value meanwhile, and
	// a clear waiting on the pick is held until the lookup settles
	drop_lookup() {
		this.lookup = null;
		this.pending_text = null;
		this.combobox.release_clear();
	}

	// the model write's promise, for a save waiting on a commit
	parse_validate_and_set_in_model(value, e) {
		return (this.last_write = super.parse_validate_and_set_in_model(value, e));
	}

	on_pick(value, option) {
		// a pick outranks text still being looked up
		this.drop_lookup();
		if (value == null) {
			// clear is a native change: route through df.change / the model
			this.$input.trigger("change");
			this.update_open_link();
			return this.last_write;
		}
		if (this.df.remember_last_selected_value) {
			frappe.boot.user.last_selected_values[this.df.options] = value;
		}
		this.title_value_map[option.label] = value;
		this.label = this.get_translated(option.label);
		// a real title only: free text (label = value) must not shadow a cached title
		if (option.label && option.label !== value) {
			frappe.utils.add_link_title(this.get_link_doctype(), value, option.label);
		}
		// one model write, through the change handler (get_input_value is the
		// picked value); the classic event follows for dialogs and MultiSelectDialog
		this.$input.trigger("change");
		this.$input.trigger("awesomplete-selectcomplete");
		return this.last_write;
	}

	// text left by clicking away or tabbing picks the listed row it names
	// exactly; anything else is dropped and the value stays
	on_close(reason) {
		this.autocomplete_open = false;
		const query = this.combobox.query;
		// a pick, even of the same value, outranks a lookup still out
		if (reason === "select") this.drop_lookup();
		// Escape cancels, a field disabled or hidden under the panel drops the
		// text; every other close commits what was typed, as blur did
		if (!query || ["escape", "select", "disabled", "hidden"].includes(reason)) return;
		// this close commits: it outranks the lookup an earlier one started
		this.drop_lookup();
		const value_at_close = this.combobox.get_value() ?? "";
		if (this.df.ignore_link_validation) {
			// any text is a value here, as in the classic control; a listed row
			// (or a known title) it names still picks that row
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
			// a pick, even of the value just cleared, ends the clear
			this.combobox.pending_clear = false;
			if (match.value === value_at_close) return;
			this.combobox.set_value(match.value, { label: match.label, image: match.image });
			return this.on_pick(match.value, match);
		};
		const match = this.combobox.match_option(query);
		if (match || !this.combobox.rows_pending) return commit(match);
		// the rows for the text hadn't arrived (a scanner, paste + Tab): look it
		// up; a clear waiting on the pick is held back until the lookup settles
		const cb = this.combobox;
		cb.hold_clear();
		this.pending_text = query;
		// a later close starts its own lookup, which owns the text and the hold
		const lookup = (this.lookup = {});
		const current = () => cb.get_value() ?? "";
		const settle = (found) => {
			// superseded: a waiting save must not fire into whatever came next
			if (this.lookup !== lookup) return false;
			this.pending_text = null;
			cb.release_clear();
			if (found) return commit(found);
			// reopened meanwhile: the next close settles the clear
			if (!cb.is_open) cb.flush_clear();
		};
		// a hook throwing at once still settles
		return new Promise((resolve) => resolve(this.fetch_options(query)))
			.then((r) => {
				// the field moved on meanwhile: changed or gone
				if (current() !== value_at_close || !document.body.contains(this.$input[0])) {
					return settle(null);
				}
				return settle(frappe.ui.Combobox.match_in(Array.isArray(r) ? r : r.rows, query));
			})
			.catch(() => settle(null));
	}
};
