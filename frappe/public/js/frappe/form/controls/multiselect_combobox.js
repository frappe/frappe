// Table MultiSelect, MultiSelectPills and MultiSelect using frappe.ui.MultiCombobox,
// used when the System Settings toggle is on.

import { mount_combobox, title_text } from "./combobox_control.js";

const classic_table = frappe.ui.form.ControlTableMultiSelect.prototype;

// click away or Tab adds the typed text, as the classic controls did on blur
function add_typed_text(control, reason, free_text) {
	const cb = control.combobox;
	const query = cb.query;
	if (!query || ["escape", "select", "disabled", "hidden"].includes(reason)) return;
	// the text was already used to tick or untick a row
	if (query === control.picked_query) return;
	const match = cb.match_option(query);
	if (match) cb.add_value(match);
	else if (free_text) cb.add_value(query);
}

// ---- Table MultiSelect: child rows, searched like a Link field ----

frappe.ui.form.ControlTableMultiSelectCombobox = class ControlTableMultiSelectCombobox extends (
	frappe.ui.form.ControlLinkCombobox
) {
	static horizontal = false;

	make() {
		super.make();
		if (this.get_link_field()?.ignore_user_permissions) {
			this.df.ignore_user_permissions = true;
		}
	}

	make_input() {
		if (this.$input) return;
		this.rows = this._get_rows() || [];
		const combobox = new frappe.ui.MultiCombobox({
			open_on_focus: true,
			arrow_keys_open: !this.grid_row,
			// a grid cell or a filter box keeps its height: the pills that don't fit show as +N
			one_line: !!this.grid_row || !!this.df.is_filter,
			filterable: false, // search_link does the filtering
			options: (query, { start }) => this.fetch_options(query, start),
			filters: () => this.get_filter_chips(),
			pill_href: (value) => this.pill_href(value),
			before_open: () => this.before_open(),
			on_open: () => {
				this.autocomplete_open = true;
				this.picked_query = null;
			},
			// Ctrl+S waits for picks still being saved
			on_close: (reason) => {
				this.autocomplete_open = false;
				add_typed_text(this, reason, false);
				return this.sync_pending ? this.sync_chain : undefined;
			},
			on_change: () => {
				this.picked_query = combobox.query;
				this.sync_model();
			},
		});
		mount_combobox(this, combobox);
		this.$input.attr("data-target", this.get_options());
	}

	// the rows model is the classic control's; only the input is new
	get_link_field() {
		return classic_table.get_link_field.call(this);
	}

	get_options() {
		return classic_table.get_options.call(this);
	}

	_get_rows() {
		return classic_table._get_rows.call(this);
	}

	_update_rows(rows) {
		return classic_table._update_rows.call(this, rows);
	}

	parse(value) {
		return classic_table.parse.call(this, value);
	}

	validate(value) {
		return classic_table.validate.call(this, value);
	}

	set_model_value(value) {
		return classic_table.set_model_value.call(this, value);
	}

	// the field shows pills, never typed text
	get_input_value() {
		return "";
	}

	set_input_value() {}

	show_selected() {}

	setup_buttons() {}

	refresh_input() {
		super.refresh_input();
		if (this.combobox) this.combobox.set_chevron(true);
	}

	set_formatted_input(value) {
		this._update_rows(value || []);
		// the pills are ahead of the model until the picks are saved
		if (!this.combobox || this.sync_pending) return;
		const values = this.row_values(value);
		this.combobox.set_value(values.map((v) => ({ value: v, label: this.pill_label(v) })));
		this.load_titles(values);
	}

	row_values(rows) {
		const link = this.get_link_field().fieldname;
		return (rows || []).map((row) => row[link]).filter((v) => v != null && v !== "");
	}

	pill_label(value) {
		const title =
			this.is_title_link() && frappe.utils.get_link_title(this.get_options(), value);
		return this.get_translated(title_text(title || value));
	}

	// titles not cached yet: fetch them, then redraw the pills
	load_titles(values) {
		const doctype = this.get_options();
		if (!this.is_title_link()) return;
		const missing = values.filter((v) => !frappe.utils.get_link_title(doctype, v));
		if (!missing.length) return;
		Promise.all(missing.map((v) => frappe.utils.fetch_link_title(doctype, v))).then(() => {
			if (!this.combobox || this.sync_pending) return;
			const current = this.combobox.get_value();
			this.combobox.set_value(current.map((v) => ({ value: v, label: this.pill_label(v) })));
		});
	}

	pill_href(value) {
		const doctype = this.get_options();
		return frappe.model.can_read(doctype) ? frappe.utils.get_form_link(doctype, value) : null;
	}

	// an app's link option that is a value is added, not set
	pick_link_option(value, label) {
		this.combobox.add_value({ value, label });
	}

	// bring the rows in line with the pills, one pick at a time
	sync_model() {
		this.sync_pending = (this.sync_pending || 0) + 1;
		this.sync_chain = (this.sync_chain || Promise.resolve())
			.then(() => this.apply_values(this.combobox.get_value()))
			.catch((error) => console.error(error))
			.then(() => {
				if (--this.sync_pending) return;
				// show what was saved: a value that failed validation drops out
				this.set_formatted_input(this._get_rows());
			});
	}

	async apply_values(values) {
		const link = this.get_link_field().fieldname;
		for (const row of (this._get_rows() || []).slice()) {
			if (!values.includes(row[link])) await this.remove_row(row);
		}
		const present = new Set(this.row_values(this._get_rows()));
		for (const value of values) {
			// adds through the classic parse: add_child, validation and the _add event
			if (!present.has(value)) await this.parse_validate_and_set_in_model(value);
		}
	}

	// the same events as the classic control's remove button
	async remove_row(row) {
		const rows = (this._get_rows() || []).filter((r) => r !== row);
		if (!this.frm) {
			await this.set_model_value(rows);
			return;
		}
		const fieldname = this.df.fieldname;
		await this.frm.script_manager.trigger(
			`before_${fieldname}_remove`,
			this.df.options,
			row.name
		);
		frappe.model.clear_doc(this.df.options, row.name);
		await this.set_model_value(rows);
		this.frm.dirty();
		await this.frm.script_manager.trigger(`${fieldname}_remove`, this.df.options, row.name);
	}
};

// ---- MultiSelectPills: a list of values from options or df.get_data(txt) ----

frappe.ui.form.ControlMultiSelectPillsCombobox = class ControlMultiSelectPillsCombobox extends (
	frappe.ui.form.ControlAutocompleteCombobox
) {
	make() {
		// the value is read before the input is made
		this.rows = [];
		super.make();
	}

	make_input() {
		if (this.$input) return;
		const combobox = new frappe.ui.MultiCombobox({
			open_on_focus: true,
			arrow_keys_open: !this.grid_row,
			// a grid cell or a filter box keeps its height: the pills that don't fit show as +N
			one_line: !!this.grid_row || !!this.df.is_filter,
			filterable: true,
			options: (query) => this.fetch_options(query),
			before_open: () => this.before_open(),
			on_open: () => {
				this.autocomplete_open = true;
				this.picked_query = null;
			},
			on_close: (reason) => {
				this.autocomplete_open = false;
				add_typed_text(this, reason, this.allows_free_text());
			},
			on_change: (values) => {
				this.picked_query = combobox.query;
				this.on_pick_values(values);
			},
		});
		mount_combobox(this, combobox);
		this.set_options();
	}

	before_open() {
		super.before_open();
		// df.get_data searches by itself: show its rows as they come
		if (this.df.get_data) this.combobox.filterable = false;
		this.asked_query = null;
	}

	fetch_options(query) {
		if (this.df.get_data) {
			return Promise.resolve(this.df.get_data(query)).then((rows) => {
				this._data = this.parse_options(rows || []);
				// get_data may ignore the text, so filter its rows as the classic control did
				const text = (query || "").toLowerCase();
				return this.to_options(this._data).filter(
					(o) =>
						!text ||
						[o.label, o.description, o.value].some((t) =>
							cstr(t).toLowerCase().includes(text)
						)
				);
			});
		}
		// a get_data override (the email composer) loads rows and calls set_data
		if (Object.prototype.hasOwnProperty.call(this, "get_data")) {
			if (query !== this.asked_query) {
				this.asked_query = query;
				this.get_data(query);
			}
			return this.to_options(this._data);
		}
		return super.fetch_options(query);
	}

	// a get_data override may load in the background and return nothing
	loaded_rows() {
		return this._data || [];
	}

	// any typed text is a value, as in the classic control (Add Tags creates new tags)
	allows_free_text() {
		return true;
	}

	// "Use …" adds the typed text and keeps the panel open
	get_footer_rows() {
		if (!this.allows_free_text()) return [];
		return [
			{
				type: "custom",
				icon: "corner-down-left",
				label: ({ query }) => __('Use "{0}"', [query]),
				keep_open: true,
				condition: ({ query }) =>
					!!query &&
					!this.rows.includes(query) &&
					!this.loaded_rows().some((d) => d.label === query || d.value === query),
				onclick: ({ query }) => {
					this.combobox.add_value(query);
					this.combobox.set_query("");
				},
			},
		];
	}

	// ---- value: a list of values ----

	get_value() {
		return this.rows;
	}

	get_values() {
		return this.rows;
	}

	get_input_value() {
		return this.rows.slice();
	}

	to_values(value) {
		if (value == null || value === "") return [];
		return Array.isArray(value) ? value.slice() : [value];
	}

	// a single value from code adds to the list, like the classic control
	parse(value) {
		if (Array.isArray(value)) return value;
		const rows = this.rows.slice();
		if (value != null && value !== "" && !rows.includes(value)) rows.push(value);
		return rows;
	}

	validate(value) {
		return value;
	}

	on_pick_values(values) {
		this.rows = values;
		this.validate_and_set_in_model(this.model_value(values));
	}

	model_value(values) {
		return values.slice();
	}

	set_formatted_input(value) {
		this.rows = this.to_values(value);
		if (!this.combobox) return;
		// a value picked before keeps the label it was shown with
		this.combobox.set_value(
			this.rows.map((v) =>
				this.combobox.picked.has(v) ? v : { value: v, label: this.label_for(v) }
			)
		);
	}

	label_for(value) {
		const item = this.loaded_rows().find((d) => d.value === value);
		const label = (item && (item.label || item.value)) || String(value);
		return this.translate_values ? __(label) : label;
	}
};

// ---- MultiSelect: the same, stored as a comma-separated string ----

frappe.ui.form.ControlMultiSelectCombobox = class ControlMultiSelectCombobox extends (
	frappe.ui.form.ControlMultiSelectPillsCombobox
) {
	get_value() {
		return this.rows.join(", ");
	}

	get_input_value() {
		return this.get_value();
	}

	to_values(value) {
		if (Array.isArray(value)) return value.slice();
		return cstr(value)
			.split(",")
			.map((v) => v.trim())
			.filter(Boolean);
	}

	parse(value) {
		return Array.isArray(value) ? value.join(", ") : cstr(value);
	}

	model_value(values) {
		return values.join(", ");
	}

	allows_free_text() {
		return !!this.df.ignore_validation || !this.loaded_rows().length;
	}

	// as the classic control: with a fixed option list, every value must be in it
	validate(value) {
		const searched = this.get_query || this.df.get_query;
		if (this.df.ignore_validation || !this.df.options || searched) return value;
		const valid = this.loaded_rows().map((d) => d.value);
		if (!valid.length) return value;
		return this.to_values(value).every((v) => valid.includes(v)) ? value : "";
	}
};
