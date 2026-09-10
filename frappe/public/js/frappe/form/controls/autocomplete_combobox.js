// Autocomplete field backed by frappe.ui.Combobox.
// Picked by make_control for Autocomplete fields when "Enable Combobox Link
// and Autocomplete Fields" is on in System Settings.

import { mount_combobox, awesomplete_shim } from "./combobox_control.js";

frappe.ui.form.ControlAutocompleteCombobox = class ControlAutocompleteCombobox extends (
	frappe.ui.form.ControlAutocomplete
) {
	make_input() {
		if (this.$input) return;

		const combobox = new frappe.ui.Combobox({
			value_input: true,
			open_on_focus: true,
			arrow_keys_open: !this.grid_row,
			// client-side filtering, unless a get_query method searches (see before_open)
			filterable: true,
			options: (query) => this.fetch_options(query),
			// free text: Tab keeps what was typed rather than the first partial
			// match, unless the arrow keys moved to a row on purpose
			tab_selects: ({ navigated }) => navigated || !this.allows_free_text(),
			before_open: () => this.before_open(),
			on_open: () => (this.autocomplete_open = true),
			on_close: (reason) => this.on_close(reason),
			on_change: (value, option) => this.on_pick(value, option),
		});

		mount_combobox(this, combobox);
		this.set_options();
	}

	// ---- classic-control surface ----

	get awesomplete() {
		// the classic validate() reads the list from _list
		return (this._awesomplete_shim ||= awesomplete_shim(this, {
			_list: { get: () => this.get_data() },
		}));
	}

	// the rows stay behind the options function, so a get_query keeps working
	set_data(data) {
		this._data = this.parse_options(data);
		if (this.combobox?.is_open) this.combobox.load();
	}

	refresh_input() {
		super.refresh_input();
		if (this.combobox && this.$input) {
			this.combobox.set_disabled(this.$input.prop("disabled"));
		}
	}

	set_formatted_input(value) {
		if (!this.combobox) return;
		// the value being cleared echoing back (a refresh) is dropped
		if (this.combobox.pending_clear && value === this.combobox.cleared_value) return;
		this.combobox.set_value(value, { label: this.format_for_input(value) });
	}

	get_input_value() {
		if (!this.combobox) return "";
		// text still being looked up after a close reads as the value
		if (this.pending_text != null) return this.pending_text;
		const value = this.combobox.value;
		return value == null ? "" : value;
	}

	// ---- rows ----

	allows_free_text() {
		return !!this.df.ignore_validation || !this.get_data().length;
	}

	to_options(data) {
		return (data || []).map((d) => ({
			label: this.translate_values ? __(d.label, null, d.parent) : d.label,
			value: d.value,
			description: d.description ? __(d.description) : undefined,
		}));
	}

	before_open() {
		const combobox = this.combobox;
		this.query_method = this.get_query || this.df.get_query || null;
		// a get_query naming a server method searches there: no client filtering then
		combobox.filterable = !this.query_args("").query;
		combobox.opts.search_placeholder = __("Search...");
		combobox.opts.footer = this.get_footer_rows();
	}

	fetch_options(query) {
		if (!this.query_method) return this.to_options(this.get_data());
		const seq = (this.query_seq = (this.query_seq || 0) + 1);
		return this.query(query).then((data) => {
			// a slower earlier response must not replace the rows for the latest text
			if (seq === this.query_seq) this._data = data;
			return this.to_options(data);
		});
	}

	query(term) {
		const args = this.query_args(term);
		if (!args.query) return Promise.resolve(this.get_data());
		return frappe.xcall(args.query, args).then((rows) => this.parse_options(rows || []));
	}

	query_args(term) {
		const args = { txt: term };
		const get_query = this.query_method;
		if (!get_query) return args;
		const apply = (obj) => {
			if (obj.query) args.query = obj.query;
			if (obj.params) Object.assign(args, obj.params);
			if (obj.translate_values !== undefined) this.translate_values = obj.translate_values;
		};
		if ($.isPlainObject(get_query)) apply(get_query);
		else if (typeof get_query === "string") args.query = get_query;
		else {
			const q = get_query(
				(this.frm && this.frm.doc) || this.doc,
				this.doctype,
				this.docname
			);
			if (typeof q === "string") args.query = q;
			else if ($.isPlainObject(q)) apply(q);
		}
		return args;
	}

	// the label is a function of the query so it follows every keystroke
	get_footer_rows() {
		if (!this.allows_free_text()) return [];
		return [
			{
				type: "custom",
				icon: "corner-down-left",
				label: ({ query }) => __('Use "{0}"', [query]),
				// only for text that isn't an option already
				condition: ({ query: q }) =>
					!!q && !this.get_data().some((d) => d.label === q || d.value === q),
				onclick: ({ query: q }) => this.commit_free_text(q),
			},
		];
	}

	commit_free_text(text) {
		this.combobox.pending_clear = false;
		this.combobox.set_value(text, { label: text });
		this.on_pick(text);
	}

	// ---- picking ----

	// a native change sets the model (see bind_change_event) and reaches
	// .on("change") listeners, as the classic control did after a pick
	drop_lookup() {
		this.lookup = null;
		this.pending_text = null;
		this.combobox.release_clear();
	}

	on_pick(value) {
		// a pick outranks text still being looked up
		this.drop_lookup();
		this.$input.trigger("change");
		if (value != null) this.$input.trigger("awesomplete-selectcomplete");
	}

	// text left by clicking away or tabbing: a label picks it, free text commits
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
		if (this.combobox.rows_pending) return this.commit_pending(query);
		const match = this.get_data().find(
			(d) => d.label.toLowerCase() === query.toLowerCase() || d.value === query
		);
		if (match) {
			// a pick, even of the value just cleared, ends the clear
			this.combobox.pending_clear = false;
			if (match.value !== this.get_input_value()) {
				this.combobox.set_value(match.value, { label: match.label });
				this.on_pick(match.value);
			}
			return;
		}
		if (this.allows_free_text() && query !== this.get_input_value()) {
			this.commit_free_text(query);
		}
	}

	// the rows for the text hadn't arrived: free text commits at once, a
	// list-only field looks the text up once (a scanner, paste + Tab)
	commit_pending(query) {
		if (this.allows_free_text()) return this.commit_free_text(query);
		const cb = this.combobox;
		const current = () => cb.value ?? "";
		const value_at_close = current();
		// a clear waiting on the pick is held back until the lookup settles
		cb.hold_clear();
		this.pending_text = query;
		// a later close starts its own lookup, which owns the text and the hold
		const lookup = (this.lookup = {});
		const settle = (match) => {
			// superseded: a waiting save must not fire into whatever came next
			if (this.lookup !== lookup) return false;
			this.pending_text = null;
			cb.release_clear();
			if (match) {
				cb.pending_clear = false;
				if (match.value === value_at_close) return;
				cb.set_value(match.value, { label: match.label });
				this.on_pick(match.value);
				return;
			}
			// reopened meanwhile: the next close settles the clear
			if (!cb.is_open) cb.flush_clear();
		};
		return this.query(query)
			.then((data) => {
				if (current() !== value_at_close) return settle(null);
				// validate() reads the list: the looked-up rows are it now
				this._data = data;
				return settle(frappe.ui.Combobox.match_in(this.to_options(data), query));
			})
			.catch(() => settle(null));
	}
};
