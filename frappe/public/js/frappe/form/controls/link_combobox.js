// Link field backed by frappe.ui.Combobox.
// Picked by make_control for Link fields when "Enable Combobox Link and
// Autocomplete Fields" is on in System Settings.

import { describe_link_filters } from "./link_filter_description.js";
import { mount_combobox, awesomplete_shim } from "./combobox_control.js";

frappe.ui.form.is_combobox_link_enabled = function () {
	// desk only; a control made before boot has no setting, so it stays classic
	if (!frappe.ui.Combobox || !frappe.sys_defaults) return false;
	return frappe.defaults.is_enabled("enable_combobox_link_field");
};

// Select mode preloads at most this many rows; longer lists fall back to Search
const PRELOAD_LIMIT = 1000;

// bounded caches: oldest entry evicted first, an overwrite counts as newest
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
const preload_fallback = new Set(); // keys whose list exceeded PRELOAD_LIMIT

// one promise per doctype + name so concurrent fields share a request
const image_promises = new Map();
const IMAGE_CACHE_MAX = 500;

function cache_key(args, extra = []) {
	const filters = typeof args.filters === "string" ? args.filters : JSON.stringify(args.filters);
	return JSON.stringify([
		args.doctype,
		filters,
		args.query,
		args.searchfield,
		args.reference_doctype,
		args.link_fieldname,
		args.ignore_user_permissions,
		...extra,
	]);
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
			// "Allow Clearing Link Fields" doesn't apply: the cross only shows on hover
			clearable: true,
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
		if (!value) {
			this.show_selected(null, "");
			return;
		}
		this.set_link_title(value);
	}

	set_input_value(text) {
		const value = text ? this.title_value_map[text] || text : null;
		this.show_selected(value, text);
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
		const avatar = this.show_image();
		const label = text || (value == null ? undefined : String(value));
		this.combobox.set_value(value, { label, avatar });
		this.update_open_link();
		if (value && avatar) {
			this.get_image(value).then((image) => {
				if (!image || this.combobox.get_value() !== value) return;
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
		return preload_fallback.has(cache_key(this.open_args)) ? "Search" : "Select";
	}

	fetch_options(query, start = 0) {
		if (!this.open_args) return [];
		if (this.open_mode !== "Search") return this.preload_options();

		// fresh copy (filters get stringified for GET); later pages keep database
		// order so scrolling doesn't reshuffle rows the user already saw
		const args = { ...this.open_args, txt: query };
		if (start) {
			args.start = start;
			args.keep_order = 1;
		}
		return this.search(args, { use_get: !query, paged: true });
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
				const raw_count = (rows || []).length;
				rows = this.merge_duplicates(rows || []);
				for (const row of rows) {
					// a bare name must not pre-empt the title fetch for title links
					if (row.label && row.label !== row.value) {
						frappe.utils.add_link_title(context.doctype, row.value, row.label);
					}
				}
				const options = rows.map((row) => this.to_option(row, context));
				// use the raw count: merging duplicates can leave a full page short
				const result = paged
					? {
							rows: options,
							has_more: !!args.page_length && raw_count >= args.page_length,
					  }
					: options;
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

		const pending = this.preload_stamp()
			.then((stamp) => {
				if (cached && cached.stamp === stamp) return cached.options;
				const args = { ...this.open_args, txt: "", page_length: PRELOAD_LIMIT + 1 };
				return Promise.resolve(this.search(args, { use_get: false, no_cache: true })).then(
					(options) => {
						if (options.length > PRELOAD_LIMIT) {
							// too long for the client: this and later opens search the server
							console.warn(
								`Link field: ${this.open_args.doctype} has more than ${PRELOAD_LIMIT} records, ` +
									`falling back to Search mode (set its Link Display Mode to Search)`
							);
							preload_fallback.add(key);
							preload_cache.delete(key);
							this.open_mode = "Search";
							this.combobox.opts.page_size = this.open_args.page_length;
							return this.fetch_options(this.combobox.query || "");
						}
						remember(preload_cache, key, { options, stamp }, PRELOAD_CACHE_MAX);
						return options;
					}
				);
			})
			.catch((error) => {
				// a failed fetch must not be served again on the next open
				preload_cache.delete(key);
				throw error;
			});
		if (!cached) {
			remember(preload_cache, key, pending, PRELOAD_CACHE_MAX);
			return pending;
		}
		// show the cached list now; reload the open panel if the rebuild differs
		pending.then((options) => {
			if (options !== cached.options && this.combobox.is_open) this.combobox.load();
		});
		return cached.options;
	}

	// one small request per open instead of a thousand-row refetch
	preload_stamp() {
		const { doctype, filters } = this.open_args;
		return frappe
			.xcall("frappe.client.get_list", {
				doctype,
				filters: filters || {},
				fields: [
					{ COUNT: "*", as: "n" },
					{ MAX: "modified", as: "m" },
				],
				limit_page_length: 1,
			})
			.then((rows) => JSON.stringify(rows && rows[0]))
			.catch(() => String(Date.now()));
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
		return descriptions.map((html) => frappe.utils.html2text(html));
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
			rows.push({
				type: "custom",
				label: item.label || frappe.utils.html2text(item.html || ""),
				onclick: () => item.action && item.action.apply(this),
			});
		}

		// no Advanced Search row: the panel pages on scroll itself
		return rows;
	}

	// ---- picking ----

	on_pick(value, option) {
		if (value == null) {
			// clear is a native change: route through df.change / the model
			this.$input.trigger("change");
			this.update_open_link();
			return;
		}
		if (this.df.remember_last_selected_value) {
			frappe.boot.user.last_selected_values[this.df.options] = value;
		}
		this.title_value_map[option.label] = value;
		this.parse_validate_and_set_in_model(value, null, option.label);
		// dialogs refresh depends_on and MultiSelectDialog reloads on this event
		this.$input.trigger("awesomplete-selectcomplete");
	}

	// text left by clicking away or tabbing is set as a docname (Escape
	// cancels); an exact name the list didn't show still gets set
	on_close(reason) {
		this.autocomplete_open = false;
		const query = this.combobox.query;
		if (!query || (reason !== "outside" && reason !== "tab")) return;
		if (query === this.$input.val() || query === this.get_input_value()) return;
		this.parse_validate_and_set_in_model(query, null);
	}
};
