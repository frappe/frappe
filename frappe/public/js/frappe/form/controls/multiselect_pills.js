import Awesomplete from "awesomplete";

frappe.ui.form.ControlMultiSelectPills = class ControlMultiSelectPills extends (
	frappe.ui.form.ControlAutocomplete
) {
	make_input() {
		super.make_input();
		this.$input_area = $(this.input_area);
		this.$multiselect_wrapper = $("<div>")
			.addClass("form-control table-multiselect")
			.appendTo(this.$input_area);

		this.$input.removeClass("form-control");
		this.$input_area.find(".awesomplete").appendTo(this.$multiselect_wrapper);

		this.$input.on("awesomplete-selectcomplete", () => {
			this.$input.val("").focus();
		});

		// used as an internal model to store values
		this.rows = [];

		this.$input_area.on("click", ".btn-remove", (e) => {
			const $target = $(e.currentTarget);
			const $value = $target.closest(".tb-selected-value");

			const value = decodeURIComponent($value.data().value);
			this.rows = this.rows.filter((val) => val !== value);

			this.parse_validate_and_set_in_model("");
		});

		this.$input.on("keydown", (e) => {
			// if backspace key pressed on empty input, delete last value
			if (e.keyCode == frappe.ui.keyCode.BACKSPACE && e.target.value === "") {
				this.rows = this.rows.slice(0, this.rows.length - 1);
				this.parse_validate_and_set_in_model("");
			}
		});
	}

	parse(value) {
		if (typeof value == "object" || !this.rows) {
			return value;
		}

		if (value) {
			this.rows.push(value);
		}

		return this.rows;
	}

	validate(value) {
		const rows = (value || []).slice();

		if (rows.length === 0) {
			return rows;
		}

		const all_rows_except_last = rows.slice(0, rows.length - 1);
		const last_value = rows[rows.length - 1];

		// falsy value
		if (!last_value) {
			return all_rows_except_last;
		}

		// duplicate value
		if (all_rows_except_last.includes(last_value)) {
			return all_rows_except_last;
		}

		return rows;
	}

	set_formatted_input(value) {
		this.rows = value || [];
		this.set_pill_html(this.rows);
	}

	set_pill_html(values) {
		const html = values.map((value) => this.get_pill_html(value)).join("");

		this.$multiselect_wrapper.find(".tb-selected-value").remove();
		this.$multiselect_wrapper.prepend(html);
	}

	get_pill_html(value) {
		const label = this.get_label(value);
		const encoded_value = encodeURIComponent(value);
		return `
			<button class="data-pill btn tb-selected-value" data-value="${encoded_value}">
				<span class="btn-link-to-form">${__(label || value)}</span>
				<span class="btn-remove">${frappe.utils.icon("close")}</span>
			</button>
		`;
	}

	get_label(value) {
		const item = this._data?.find((d) => d.value === value);
		return item ? item.label || item.value : null;
	}

	get_awesomplete_settings() {
		const settings = super.get_awesomplete_settings();

		return Object.assign(settings, {
			filter: function (text, input) {
				let d = this.get_item(text.value);
				if (!d) {
					return Awesomplete.FILTER_CONTAINS(text, input.match(/[^,]*$/)[0]);
				}

				let getMatch = (value) =>
					Awesomplete.FILTER_CONTAINS(value, input.match(/[^,]*$/)[0]);

				// match typed input with label or value or description
				let v = getMatch(d.label);
				if (!v && d.value) {
					v = getMatch(d.value);
				}
				if (!v && d.description) {
					v = getMatch(d.description);
				}

				return v;
			},
		});
	}

	get_value() {
		return this.rows;
	}

	get_values() {
		return this.rows;
	}

	get_data() {
		let data;
		if (this.df.get_data) {
			let txt = this.$input.val();
			data = this.df.get_data(txt);
			if (data && data.then) {
				data.then((r) => {
					this.set_data(r);
				});
				data = this.get_value();
			} else {
				this.set_data(data);
			}
		} else {
			data = super.get_data();
		}
		const values = this.get_values() || [];

		// return values which are not already selected
		if (data) data.filter((d) => !values.includes(d));
		return data;
	}
};
