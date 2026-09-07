// Link field rendered with frappe.ui.Combobox: a trigger styled like the
// input it replaces, and a panel with the search box inside, two-line rows
// (title over docname), optional avatars, filter chips, and the Create row
// (plus any app hook rows) in the footer.
//
// Picked by make_control for Link fields when System Settings > "Enable
// Combobox Link Field" is on, or when a developer sets
// localStorage.combobox_link_field = "1" for their own browser.
//
// Compatibility: this class extends the classic ControlLink and keeps its
// public surface — set_value / get_value / get_input_value / get_label_value,
// $input (a real, read-only <input> inside the trigger), get_query and every
// filter option, fetch_from, validate_link_and_fetch, new_doc,
// open_advanced_search, title handling, translations and the static
// link_options hook. Only the widget under make_input changes. The classic
// control itself stays untouched for customizations that reach into its
// internals (a small `awesomplete` shim covers open/close/ul).

import { describe_link_filters } from "./link_filter_description.js";

frappe.ui.form.is_combobox_link_enabled = function () {
	// desk only: the component and the boot data live in desk.bundle.js, so
	// web forms (controls.bundle.js on the website) keep the classic control
	if (!frappe.ui.Combobox || !frappe.defaults?.is_enabled || !frappe.sys_defaults) return false;
	try {
		const override = window.localStorage?.getItem("combobox_link_field");
		if (override === "1") return true;
		if (override === "0") return false;
	} catch (e) {
		// storage blocked: fall through to the site setting
	}
	return frappe.defaults.is_enabled("enable_combobox_link_field");
};

// Preload / Select modes fetch this many rows at most; a list that turns
// out longer is searched on the server instead
const PRELOAD_LIMIT = 1000;

// module caches: bounded, oldest entry evicted first
function remember(map, key, value, max) {
	if (map.size >= max) map.delete(map.keys().next().value);
	map.set(key, value);
}

// search results per doctype + filters + query + page, so retyping a term or
// reopening a field doesn't hit the server again (the classic control kept
// the same per-term cache); a short life keeps new records from hiding
const search_cache = new Map(); // key -> { result, time }
const SEARCH_CACHE_MS = 60 * 1000;
const SEARCH_CACHE_MAX = 200;

// Preload / Select: the whole list per doctype + filters, with the record
// count and latest modification it was built from. A cheap check of those on
// every open says whether it must be rebuilt. (A push channel would be
// fragile here: list views drop every list_update listener and the doctype
// room whenever they refresh.)
const preload_cache = new Map(); // key -> { options, stamp } or a pending Promise
const PRELOAD_CACHE_MAX = 20;
const preload_fallback = new Set(); // keys whose list exceeded PRELOAD_LIMIT

// avatar (image_field value) per doctype + name, as a promise so concurrent
// fields for the same record share one request and search results seed it
const image_promises = new Map();
const IMAGE_CACHE_MAX = 500;

// what makes two searches interchangeable: everything the server filters or
// permission-checks by, with the filters in one canonical string form
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
	static trigger_change_on_input_event = false;

	// the module caches, for tests and for apps that change records outside
	// the desk's own flows
	static caches = { search: search_cache, preload: preload_cache, images: image_promises };
	static clear_caches() {
		search_cache.clear();
		preload_cache.clear();
		preload_fallback.clear();
		image_promises.clear();
	}

	make_input() {
		if (this.$input) return;
		this.title_value_map = this.title_value_map || {};

		this.combobox = new frappe.ui.Combobox({
			value_input: true,
			filterable: false, // search_link does the filtering
			// always clearable: the cross only shows on hover / focus / open,
			// so the "Allow Clearing Link Fields" setting (meant for the
			// classic control's always-visible button) doesn't apply here
			clearable: true,
			options: (query, { start }) => this.fetch_options(query, start),
			filters: () => this.get_filter_chips(),
			actions: [
				{ icon: "arrow-right", title: __("Open Link"), href: "#", css_class: "btn-open" },
			],
			before_open: () => this.before_open(),
			// grid_row.js reads this flag to leave arrow keys to the dropdown
			on_open: () => (this.autocomplete_open = true),
			on_close: (reason) => this.on_close(reason),
			on_change: (value, option) => this.on_pick(value, option),
		});

		this.$input_area = $(this.input_area);
		this.combobox.$trigger.prependTo(this.input_area);
		this.$input = $(this.combobox.input_el);
		// same hooks as the classic input: .input-with-feedback is what
		// dialogs and MultiSelectDialog bind their change listeners to
		this.$input.addClass("input-with-feedback").attr("data-target", this.df.options);
		this.set_input_attributes();
		this.input = this.$input.get(0);
		this.has_input = true;
		this.translate_values = true;

		// the classic control's button handles, for code that toggles them
		this.$link = $(this.combobox.actions_el);
		this.$link_open = $(this.combobox.action_els[0]);
		this.$link_clear = $(this.combobox.clear_btn);
		this.setup_buttons();
		this.update_open_link();

		this.bind_change_event();
	}

	// ---- classic-control surface ----

	// the awesomplete widget is gone; this covers what other desk code calls
	// on it: grid.js closes it on scroll, ERPNext's POS restyles its list
	get awesomplete() {
		if (!this._awesomplete_shim) {
			const me = this;
			this._awesomplete_shim = {
				open: () => me.combobox && me.combobox.open(),
				close: () => me.combobox && me.combobox.close("owner"),
				get opened() {
					return !!(me.combobox && me.combobox.is_open);
				},
				get ul() {
					return (me.combobox && me.combobox.list_el) || document.createElement("ul");
				},
			};
		}
		return this._awesomplete_shim;
	}

	setup_buttons() {
		if (this.only_input && !this.with_link_btn) {
			this.$link_open.remove();
		}
	}

	// the target doctype, or null while it can't be resolved (a Dynamic Link
	// whose type field is empty or points at a Single, a list page whose
	// filter isn't built yet). The classic control only resolves it when the
	// user searches; display code must not throw before that.
	get_link_doctype() {
		try {
			return this.get_options() || null;
		} catch (e) {
			return null;
		}
	}

	// every value from the model goes through here (the classic version
	// writes $input.val() first, which the combobox would overwrite anyway)
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

	// the typed query while the panel is open (quick entry pre-fills the
	// name with it), else the shown title
	get_label_value() {
		if (this.combobox && this.combobox.is_open) return this.combobox.query || "";
		return this.$input ? this.$input.val() : "";
	}

	// kept for scripts that call it on the classic control; the footer no
	// longer offers it. Seeded with what the user typed, not the value picked
	open_advanced_search() {
		const doctype = this.get_link_doctype();
		if (!doctype) return;
		new frappe.ui.form.LinkSelector({
			doctype,
			target: this,
			txt: this.get_label_value(),
		});
		return false;
	}

	show_link_and_clear_buttons() {
		this.update_open_link();
	}

	hide_link_and_clear_buttons() {
		// the combobox shows its buttons on hover / focus by itself
	}

	toggle_href(doctype) {
		this.update_open_link(doctype);
	}

	refresh_input() {
		super.refresh_input();
		if (this.combobox && this.$input) {
			this.combobox.set_disabled(this.$input.prop("disabled"));
		}
	}

	// ---- display ----

	show_selected(value, text) {
		if (!this.combobox) return;
		const show_image = this.show_image();
		this.combobox.set_value(value, {
			label: text || (value == null ? undefined : String(value)),
			avatar: show_image,
		});
		this.update_open_link();
		if (value && show_image) {
			this.get_image(value).then((image) => {
				if (!image || this.combobox.get_value() !== value) return;
				this.combobox.set_value(value, { label: text, image, avatar: true });
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

	show_image() {
		return !!this.link_settings().show_image;
	}

	// the image_field value for one record, by name: boot tells us the field,
	// so the DocType's meta needn't be loaded on this form. One promise per
	// doctype + name, seeded by search results (see to_option)
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
		// get_value needs read permission; a select-only user gets no avatar
		// rather than a "not permitted" dialog
		if (!frappe.model.can_read(doctype)) return Promise.resolve(null);
		return frappe.db
			.get_value(doctype, name, image_field)
			.then((r) => (r.message || {})[image_field] || null)
			.catch(() => null);
	}

	// ---- panel content ----

	// "Search" (the default): the server filters per keystroke and pages on
	// scroll. "Preload": the whole list once, filtered on the client.
	// "Select": Preload without the search box, for short lists.
	display_mode() {
		return this.link_settings().display_mode || "Search";
	}

	// the search arguments (filters, query method...) for this open, computed
	// once: get_query functions can be costly and must see the same state for
	// the rows and for the filter chips
	before_open() {
		// unguarded on purpose: a Dynamic Link pointing at a Single raises
		// the same "not a valid DocType" message the classic control shows
		// when the user starts searching
		const doctype = this.get_options() || null;
		const combobox = this.combobox;
		this.open_args = this.get_search_args("") || null;
		this.open_mode = this.display_mode();
		// a list that once exceeded PRELOAD_LIMIT is searched instead
		if (
			this.open_mode !== "Search" &&
			this.open_args &&
			preload_fallback.has(cache_key(this.open_args))
		) {
			this.open_mode = "Search";
		}
		combobox.opts.search_placeholder = __("Search {0}...", [__(doctype || "")]);
		combobox.opts.footer = this.get_footer_rows();
		combobox.opts.hide_search = this.open_mode === "Select";
		combobox.filterable = this.open_mode !== "Search";
		combobox.opts.page_size =
			this.open_mode === "Search" && this.open_args ? this.open_args.page_length : null;
	}

	fetch_options(query, start = 0) {
		if (!this.open_args) return [];
		if (this.open_mode !== "Search") return this.preload_options();

		// a fresh copy per request: the filters get stringified for GET below.
		// The first page is re-sorted by relevance like the classic dropdown
		// (prefix matches first); later pages must stay in database order,
		// or scrolling would reshuffle rows the user already looked at
		const args = { ...this.open_args, txt: query };
		if (start) {
			args.start = start;
			args.keep_order = 1;
		}
		return this.search(args, { use_get: !query, paged: true });
	}

	// one search_link call, through the short-lived result cache (unless the
	// caller keeps its own, like preload_options). `paged` answers with
	// { rows, has_more } so the combobox knows whether to fetch another page
	search(args, { use_get, no_cache, paged } = {}) {
		const doctype = args.doctype;
		if (this.show_image()) args.include_image = 1;

		// GET (browser-cacheable) for the empty query with small filters,
		// same as the classic control. A field that just created a record
		// skips every cache once, so the new record shows up right away
		const created_new = !!this.$input._created_new_doc;
		use_get = use_get && !created_new;
		if (use_get) {
			const [too_large, filters_str] = this.are_filters_large(args.filters);
			use_get = !too_large;
			args.filters = filters_str;
		}

		const key = cache_key(args, [
			args.txt,
			args.start || 0,
			args.page_length,
			args.include_image,
		]);
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
				this.toggle_href(doctype);
				for (const row of rows) {
					frappe.utils.add_link_title(doctype, row.value, row.label);
				}
				const options = rows.map((row) => this.to_option(row));
				// has_more from the server's own count: merging duplicate rows
				// can leave a full page looking short
				const result = paged
					? { rows: options, has_more: raw_count >= (args.page_length || 0) }
					: options;
				remember(search_cache, key, { result, time: Date.now() }, SEARCH_CACHE_MAX);
				return result;
			});
	}

	// Preload / Select: the whole list for this doctype + filters, rebuilt
	// only when the record count or latest modification changed. The cached
	// list shows at once; a rebuild replaces it when it lands.
	preload_options() {
		const key = cache_key(this.open_args, [this.show_image()]);
		const cached = this.$input._created_new_doc ? null : preload_cache.get(key);
		// a fetch already under way (the user typed before it landed): share it
		if (cached && typeof cached.then === "function") return cached;

		const pending = this.preload_stamp().then((stamp) => {
			if (cached && cached.stamp === stamp) return cached.options;
			const args = { ...this.open_args, txt: "", page_length: PRELOAD_LIMIT + 1 };
			return Promise.resolve(this.search(args, { use_get: false, no_cache: true })).then(
				(options) => {
					if (options.length > PRELOAD_LIMIT) {
						// too long to hold on the client: this and every later
						// open search the server instead
						console.warn(
							`Link field: ${this.open_args.doctype} has more than ${PRELOAD_LIMIT} records, ` +
								`falling back to Search mode (set its Link Display Mode to Search)`
						);
						preload_fallback.add(cache_key(this.open_args));
						preload_cache.delete(key);
						this.open_mode = "Search";
						this.combobox.filterable = false;
						this.combobox.opts.page_size = this.open_args.page_length;
						return this.fetch_options(this.combobox.query || "");
					}
					remember(preload_cache, key, { options, stamp }, PRELOAD_CACHE_MAX);
					return options;
				}
			);
		});
		if (!cached) {
			remember(preload_cache, key, pending, PRELOAD_CACHE_MAX);
			return pending;
		}
		// the cached list shows now; if the rebuild brings a new one, the
		// open panel reloads to show it
		pending.then((options) => {
			if (options !== cached.options && this.combobox.is_open) this.combobox.load();
		});
		return cached.options;
	}

	// count + latest modification of the records the preloaded list covers:
	// one small request per open, versus a thousand-row refetch
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

	to_option(row) {
		const label = this.get_translated(row.label || row.value);
		let description = row.description;
		// a bare docname under an identical label says nothing; title links
		// keep it because the name isn't visible otherwise
		if (description && !this.is_title_link() && description === row.value) {
			description = null;
		}
		if (description) description = __(frappe.utils.html2text(description));
		const show_image = this.show_image();
		if (show_image) {
			// the result carries the image: no by-name fetch needed later
			const key = `${this.get_link_doctype()}::${row.value}`;
			remember(image_promises, key, Promise.resolve(row.image || null), IMAGE_CACHE_MAX);
		}
		return { label, value: row.value, description, image: row.image, avatar: show_image };
	}

	// one chip per applied filter, from the same describer the classic
	// dropdown uses for its "Filtered by" line
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

		// custom link actions registered by apps (same hook as the classic control)
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

		// no Advanced Search row: the panel searches, pages on scroll and shows
		// descriptions itself; grids bulk-add rows through "Add Multiple"
		return rows;
	}

	// ---- picking ----

	on_pick(value, option) {
		if (value == null) {
			// the classic clear was "empty the input and blur", i.e. a native
			// change: route through the same handler (df.change or the model)
			this.$input.trigger("change");
			this.update_open_link();
			return;
		}
		if (this.df.remember_last_selected_value) {
			frappe.boot.user.last_selected_values[this.df.options] = value;
		}
		this.title_value_map[option.label] = value;
		this.parse_validate_and_set_in_model(value, null, option.label);
		// what the classic dropdown dispatched after a pick; dialogs refresh
		// depends_on and MultiSelectDialog reloads its results on it
		this.$input.trigger("awesomplete-selectcomplete");
	}

	// typed text left behind by clicking away or tabbing on (not Escape:
	// that is a cancel) is validated as a docname, the way the classic
	// control validated its input on blur — an exact name the list didn't
	// show (still loading, past the first page) still gets set
	on_close(reason) {
		this.autocomplete_open = false;
		const query = this.combobox.query;
		if (!query || (reason !== "outside" && reason !== "tab")) return;
		if (query === this.$input.val() || query === this.get_input_value()) return;
		this.parse_validate_and_set_in_model(query, null);
	}
};
