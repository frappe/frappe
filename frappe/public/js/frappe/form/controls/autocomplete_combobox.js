// Autocomplete field using frappe.ui.Combobox, used when the System Settings toggle is on.

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
			// filter in the browser, unless get_query searches on the server
			filterable: true,
			options: (query) => this.fetch_options(query),
			// with free text, Tab keeps the typed text unless a row was chosen with arrows
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
		// classic validate() reads _list
		return (this._awesomplete_shim ||= awesomplete_shim(this, {
			_list: { get: () => this.get_data() },
		}));
	}

	// use a function so get_query still works
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
		// ignore the old value coming back during a clear
		if (this.combobox.pending_clear && value === this.combobox.cleared_value) return;
		this.combobox.set_value(value, { label: this.format_for_input(value) });
	}

	get_input_value() {
		if (!this.combobox) return "";
		// typed text still being checked counts as the value
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
			// a row given only a value shows the value, as the classic control does
			label: this.translate_values
				? __(d.label || d.value, null, d.parent)
				: d.label || d.value,
			value: d.value,
			description: d.description ? __(d.description) : undefined,
		}));
	}

	before_open() {
		const combobox = this.combobox;
		this.query_method = this.get_query || this.df.get_query || null;
		// get_query with a server method: search on the server
		combobox.filterable = !this.query_args("").query;
		combobox.opts.search_placeholder = __("Search...");
		combobox.opts.footer = this.get_footer_rows();
	}

	fetch_options(query) {
		if (!this.query_method) return this.to_options(this.get_data());
		const seq = (this.query_seq = (this.query_seq || 0) + 1);
		return this.query(query).then((data) => {
			// ignore late responses for older text
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

	// label updates as the user types
	get_footer_rows() {
		if (!this.allows_free_text()) return [];
		return [
			{
				type: "custom",
				icon: "corner-down-left",
				label: ({ query }) => __('Use "{0}"', [query]),
				// only when the text isn't already an option
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

	// trigger change so the value is set and .on("change") listeners run
	drop_lookup() {
		this.lookup = null;
		this.pending_text = null;
		this.combobox.release_clear();
	}

	on_pick(value) {
		// a pick cancels the typed text check
		this.drop_lookup();
		this.$input.trigger("change");
		if (value != null) this.$input.trigger("awesomplete-selectcomplete");
	}

	// on click away or Tab: a matching label is picked, else free text is saved
	on_close(reason) {
		this.autocomplete_open = false;
		const query = this.combobox.query;
		// a pick cancels the typed text check
		if (reason === "select") this.drop_lookup();
		// Escape, disabled or hidden drop the text; other closes save it
		if (!query || ["escape", "select", "disabled", "hidden"].includes(reason)) return;
		// cancel the check started by an earlier close
		this.drop_lookup();
		if (this.combobox.rows_pending) return this.commit_pending(query);
		const match = this.get_data().find(
			(d) => d.label.toLowerCase() === query.toLowerCase() || d.value === query
		);
		if (match) {
			// any pick ends the clear
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

	// rows not loaded yet: save free text now, or look the text up
	commit_pending(query) {
		if (this.allows_free_text()) return this.commit_free_text(query);
		const cb = this.combobox;
		const current = () => cb.value ?? "";
		const value_at_close = current();
		// keep the clear waiting until the check is done
		cb.hold_clear();
		this.pending_text = query;
		// a later close starts its own check
		const lookup = (this.lookup = {});
		const settle = (match) => {
			// outdated: don't let a waiting save run
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
			// reopened: the next close finishes the clear
			if (!cb.is_open) cb.flush_clear();
		};
		return this.query(query)
			.then((data) => {
				if (current() !== value_at_close) return settle(null);
				// validate() reads this list
				this._data = data;
				return settle(frappe.ui.Combobox.match_in(this.to_options(data), query));
			})
			.catch(() => settle(null));
	}
};
