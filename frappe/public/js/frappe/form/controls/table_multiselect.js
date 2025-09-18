frappe.ui.form.ControlTableMultiSelect = class ControlTableMultiSelect extends (
	frappe.ui.form.ControlLink
) {
	static horizontal = false;
	make_input() {
		super.make_input();
		this.$input_area.addClass("form-control table-multiselect");
		this.$input.removeClass("form-control");

		this.$input.on("awesomplete-selectcomplete", () => {
			this.$input.val("").focus();
		});

		// used as an internal model to store values
		this.rows = [];
		// used as an internal model to filter awesomplete values
		this._rows_list = [];

		this.$input_area.on("click", (e) => {
			if (e.target === this.$input_area.get(0)) {
				this.$input.focus();
			}
		});

		this.$input_area.on("click", ".btn-remove", (e) => {
			const $target = $(e.currentTarget);
			const $value = $target.closest(".tb-selected-value");

			const value = decodeURIComponent($value.data().value);
			const link_field = this.get_link_field();
			this.rows = this.rows.filter((row) => {
				if (row[link_field.fieldname] !== value) {
					return row;
				} else {
					frappe.run_serially([
						() => {
							return this.frm.script_manager.trigger(
								`before_${this.df.fieldname}_remove`,
								this.df.options,
								row.name
							);
						},
						() => {
							frappe.model.clear_doc(this.df.options, row.name);

							this.frm.dirty();
							this.refresh();

							return this.frm.script_manager.trigger(
								`${this.df.fieldname}_remove`,
								this.df.options,
								row.name
							);
						},
					]);
				}
			});
		});
		this.$input_area.on("click", ".btn-link-to-form", (e) => {
			const $target = $(e.currentTarget);
			const $value = $target.closest(".tb-selected-value");

			const value = decodeURIComponent($value.data().value);
			const link_field = this.get_link_field();
			frappe.set_route("Form", link_field.options, value);
		});
		this.$input.on("keydown", (e) => {
			// if backspace key pressed on empty input, delete last value
			if (e.keyCode == frappe.ui.keyCode.BACKSPACE && e.target.value === "") {
				this.rows = this.rows.slice(0, this.rows.length - 1);
				this.parse_validate_and_set_in_model("");
			}
		});
	}
	setup_buttons() {
		this.$input_area.find(".link-btn").remove();
	}
	parse(value, label) {
		if (typeof value == "object" || !this.rows) {
			return value;
		}

		const link_field = this.get_link_field();

		if (value) {
			// Trim the value to remove spaces or only if space is only input
			value = value.trim();

			// Only create a pill if the value is a real item from the autocomplete list.
			// This prevents creating a pill from raw text when the user clicks away.
			if (this.awesomplete.get_item(value)) {
				if (this.frm) {
					const new_row = frappe.model.add_child(
						this.frm.doc,
						this.df.options,
						this.df.fieldname
					);
					new_row[link_field.fieldname] = value;
					this.rows = this.frm.doc[this.df.fieldname];

					this.frm.script_manager.trigger(
						`${this.df.fieldname}_add`,
						this.df.options,
						new_row.name
					);
				} else {
					this.rows.push({
						[link_field.fieldname]: value,
					});
				}
				frappe.utils.add_link_title(link_field.options, value, label);
			}
		}
		this._rows_list = this.rows.map((row) => row[link_field.fieldname]);
		return this.rows;
	}
	get_model_value() {
		let value = super.get_model_value();
		return value ? value.filter((d) => !d.__islocal) : value;
	}
	validate(value) {
		const rows = (value || []).slice();

		// validate the value just entered
		if (this.df.ignore_link_validation) {
			return rows;
		}

		const link_field = this.get_link_field();
		if (rows.length === 0) {
			return rows;
		}

		const all_rows_except_last = rows.slice(0, rows.length - 1);
		const last_row = rows[rows.length - 1];

		// validate the last value entered
		const link_value = last_row[link_field.fieldname];

		// falsy value
		if (!link_value) {
			return all_rows_except_last;
		}

		// duplicate value
		if (all_rows_except_last.map((row) => row[link_field.fieldname]).includes(link_value)) {
			return all_rows_except_last;
		}

		return this.validate_link_and_fetch(link_value).then((validated_value) => {
			if (validated_value === link_value) {
				return rows;
			} else {
				rows.pop();
				return rows;
			}
		});
	}
	set_formatted_input(value) {
		this.rows = value || [];
		const link_field = this.get_link_field();
		const values = this.rows.map((row) => row[link_field.fieldname]);
		this.set_pill_html(values);
	}
	set_pill_html(values) {
		const html = values.map((value) => this.get_pill_html(value)).join("");

		this.$input_area.find(".tb-selected-value").remove();
		this.$input_area.prepend(html);
	}
	get_pill_html(value) {
		const link_field = this.get_link_field();
		const encoded_value = encodeURIComponent(value);
		const pill_name = frappe.utils.get_link_title(link_field.options, value) || value;

		return `
			<button class="data-pill btn tb-selected-value" data-value="${encoded_value}">
				<span class="btn-link-to-form">${__(frappe.utils.escape_html(pill_name))}</span>
				<span class="btn-remove">${frappe.utils.icon("close")}</span>
			</button>
		`;
	}
	get_options() {
		return (this.get_link_field() || {}).options;
	}
	get_link_field() {
		if (!this._link_field) {
			const meta = frappe.get_meta(this.df.options);
			this._link_field = meta?.fields?.find((df) => df.fieldtype === "Link");
			if (!this._link_field) {
				throw new Error("Table MultiSelect requires a Table with atleast one Link field");
			}
		}
		return this._link_field;
	}
	custom_awesomplete_filter(awesomplete) {
		let me = this;

		awesomplete.filter = function (item) {
			if (me._rows_list.includes(item.value)) {
				return false;
			}

			return true;
		};
	}
	get_input_value() {
		return this.$input ? this.$input.val() : undefined;
	}
	update_value() {
		let value = this.get_input_value();

		if (value !== this.last_value) {
			this.parse_validate_and_set_in_model(value);
		}
	}
};
