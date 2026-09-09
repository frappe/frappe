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
			clearable: true,
			// client-side filtering, unless a get_query method searches (see before_open)
			filterable: true,
			options: (query) => this.fetch_options(query),
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
		this.combobox.set_value(value, { label: this.format_for_input(value) });
	}

	get_input_value() {
		if (!this.combobox) return "";
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
		// a get_query method searches on the server: no client filtering then
		combobox.filterable = !this.query_method;
		combobox.opts.search_placeholder = __("Search...");
		combobox.opts.footer = this.get_footer_rows();
	}

	fetch_options(query) {
		if (!this.query_method) return this.to_options(this.get_data());
		return this.query(query).then((data) => {
			this._data = data;
			return this.to_options(data);
		});
	}

	query(term) {
		const args = { txt: term };
		const get_query = this.query_method;
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
		if (!args.query) return Promise.resolve(this.get_data());
		return frappe.xcall(args.query, args).then((rows) => this.parse_options(rows || []));
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
		this.combobox.set_value(text, { label: text });
		this.on_pick(text);
	}

	// ---- picking ----

	// a native change sets the model (see bind_change_event) and reaches
	// .on("change") listeners, as the classic control did after a pick
	on_pick(value) {
		this.$input.trigger("change");
		if (value != null) this.$input.trigger("awesomplete-selectcomplete");
	}

	// text left by clicking away or tabbing: a label picks it, free text commits
	on_close(reason) {
		this.autocomplete_open = false;
		const query = this.combobox.query;
		if (!query || (reason !== "outside" && reason !== "tab")) return;
		// the rows for the text hadn't arrived: the list can't be judged yet
		if (this.combobox.rows_pending) return;
		const match = this.get_data().find(
			(d) => d.label.toLowerCase() === query.toLowerCase() || d.value === query
		);
		if (match) {
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
};
