// The Autocomplete field rendered with frappe.ui.Combobox, the same widget
// the Link field uses under the same System Setting. The list comes from
// df.options (a newline list, JSON, an array of {label, value, description})
// or a get_query method; set_data() swaps it at runtime as before.
//
// Free text: the classic control accepts any typed text when
// df.ignore_validation is set or the list is empty — otherwise a value not
// in the list validates to "". Here the panel offers the typed text as a
// "Use …" row in that case, and tabbing or clicking away commits it; a
// list-only field just drops text that matches nothing.
//
// Compatibility: extends the classic ControlAutocomplete and keeps its
// surface — set_data / get_data / parse_options / format_for_input /
// get_input_value / validate, translate_values, and the awesomplete /
// autocomplete_open handles grid rows and dialogs read.

frappe.ui.form.ControlAutocompleteCombobox = class ControlAutocompleteCombobox extends (
	frappe.ui.form.ControlAutocomplete
) {
	static trigger_change_on_input_event = false;

	make_input() {
		if (this.$input) return;

		this.combobox = new frappe.ui.Combobox({
			value_input: true,
			open_on_focus: true,
			arrow_keys_open: !this.grid_row,
			clearable: true,
			// the rows are the field's own list: filtered on the client, unless
			// a get_query method does the searching (see before_open)
			filterable: true,
			options: (query) => this.fetch_options(query),
			before_open: () => this.before_open(),
			on_open: () => (this.autocomplete_open = true),
			on_close: (reason) => this.on_close(reason),
			on_change: (value, option) => this.on_pick(value, option),
		});

		this.$input_area = $(this.input_area);
		this.combobox.$trigger.data("es-combobox", this.combobox);
		this.combobox.$trigger.prependTo(this.input_area);
		this.$input = $(this.combobox.input_el);
		this.$input.addClass("input-with-feedback");
		this.set_input_attributes();
		this.input = this.$input.get(0);
		this.has_input = true;
		this.bind_change_event();

		this.set_options();
	}

	// ---- classic-control surface ----

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
				// validate() on the classic control reads the list from here
				get _list() {
					return me.get_data();
				},
			};
		}
		return this._awesomplete_shim;
	}

	set_data(data) {
		data = this.parse_options(data);
		this._data = data;
		if (this.combobox) this.combobox.set_options(this.to_options(data));
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

	// the picked value itself (free text included); the classic control had
	// to map the input's label back to a value
	get_input_value() {
		if (!this.combobox) return "";
		const value = this.combobox.value;
		return value == null ? "" : value;
	}

	validate(value) {
		if (this.df.ignore_validation) return value || "";
		const valid = this.get_data().map((d) => d.value);
		if (!valid.length) return value;
		return valid.includes(value) ? value : "";
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

	// the classic execute_query_if_exists, as a promise of parsed rows
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

	// the "Use …" row names the typed text: its label is a function of the
	// query, so it follows every keystroke
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
		this.parse_validate_and_set_in_model(text);
		this.$input.trigger("awesomplete-selectcomplete");
	}

	// ---- picking ----

	on_pick(value, option) {
		if (value == null) {
			this.$input.trigger("change");
			return;
		}
		this.parse_validate_and_set_in_model(value);
		this.$input.trigger("awesomplete-selectcomplete");
	}

	// typed text left behind by clicking away or tabbing on: an option's
	// exact label picks it, free text is committed where allowed, anything
	// else is dropped (the field keeps its value)
	on_close(reason) {
		this.autocomplete_open = false;
		const query = this.combobox.query;
		if (!query || (reason !== "outside" && reason !== "tab")) return;
		const match = this.get_data().find(
			(d) => d.label.toLowerCase() === query.toLowerCase() || d.value === query
		);
		if (match) {
			if (match.value !== this.get_input_value()) {
				this.combobox.set_value(match.value, { label: match.label });
				this.on_pick(match.value, match);
			}
			return;
		}
		if (this.allows_free_text() && query !== this.get_input_value()) {
			this.commit_free_text(query);
		}
	}
};
