frappe.ui.form.ControlTableMultiSelect = class ControlTableMultiSelect extends (
	frappe.ui.form.ControlLink
) {
	static horizontal = false;
	make() {
		// parent element
		super.make();
		const link_field = this.get_link_field();
		if (link_field?.ignore_user_permissions) {
			this.df.ignore_user_permissions = true;
		}
	}
	make_input() {
		super.make_input();
		this.$input_area.addClass("form-control table-multiselect");
		this.$input.removeClass("form-control");

		this.$input.on("awesomplete-selectcomplete", () => {
			this.$input.val("").focus();
		});

		// used as an internal model to store values
		this.rows = this._get_rows() || [];
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
			const rows = this._get_rows().filter((row) => {
				if (row[link_field.fieldname] !== value) return row;

				frappe.run_serially([
					() => {
						return this.frm?.script_manager.trigger(
							`before_${this.df.fieldname}_remove`,
							this.df.options,
							row.name
						);
					},
					() => {
						frappe.model.clear_doc(this.df.options, row.name);

						this.frm?.dirty();
						this.refresh();

						return this.frm?.script_manager.trigger(
							`${this.df.fieldname}_remove`,
							this.df.options,
							row.name
						);
					},
				]);
			});
			this._update_rows(rows);
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
				const rows = this._get_rows().slice(0, -1);
				this.parse_validate_and_set_in_model(rows);
			}
		});
	}
	_get_rows() {
		return this.get_model_value() || this.rows;
	}
	_update_rows(rows) {
		this.rows = rows;

		const link_fieldname = this.get_link_field().fieldname;
		this._rows_list = rows.map((row) => row[link_fieldname]);

		return rows;
	}
	setup_buttons() {
		this.$input_area.find(".link-btn").remove();
	}
	parse(value) {
		let rows = this._get_rows();

		if (typeof value == "object" || !rows) {
			return value;
		}

		const link_field = this.get_link_field();
		value = value?.trim();
		if (!value) return rows;

		// clear input to prevent multiple additions
		this.set_input_value("");

		let new_row;
		if (this.frm) {
			new_row = frappe.model.add_child(this.frm.doc, this.df.options, this.df.fieldname);
			new_row[link_field.fieldname] = value;

			// to ensure we pop from the correct rows array
			rows = this.get_model_value();
			rows.pop();
		} else {
			new_row = {
				[link_field.fieldname]: value,
			};
		}

		return [...rows, new_row];
	}
	async validate(value) {
		const rows = (value || []).slice();

		if (rows.length === 0) {
			return rows;
		}

		const all_rows_except_last = rows.slice(0, rows.length - 1);
		const last_row = rows[rows.length - 1];
		const link_field = this.get_link_field();

		// validate the last value entered
		const link_value = last_row[link_field.fieldname];

		// falsy / duplicate value
		if (
			frappe.utils.is_empty(link_value) ||
			all_rows_except_last.map((row) => row[link_field.fieldname]).includes(link_value)
		) {
			return all_rows_except_last;
		}

		if (!this.df.ignore_link_validation) {
			const validated_value = await this.validate_link_and_fetch(link_value);
			if (frappe.utils.is_empty(validated_value)) {
				return all_rows_except_last;
			}
			last_row[link_field.fieldname] = validated_value;
		}

		return rows;
	}
	async set_model_value(value) {
		const old_length = this._get_rows()?.length || 0;
		const new_length = value?.length || 0;
		const result = super.set_model_value(...arguments);
		this._update_rows(value);

		if (new_length - old_length === 1 && this.frm) {
			// trigger add event only if one row is added
			const new_row = value[value.length - 1];
			await this.frm.script_manager.trigger(
				`${this.df.fieldname}_add`,
				this.df.options,
				new_row.name
			);
		}
		return result;
	}
	set_formatted_input(value) {
		const link_field = this.get_link_field();
		const values = (value || []).map((row) => row[link_field.fieldname]);
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
