frappe.ui.form.ControlLinkMultiSelect = frappe.ui.form.ControlLink.extend({
	make_input() {
		this._super();

		this.$input_area.addClass('form-control table-multiselect');
		this.$input.removeClass('form-control');

		this.$input.on("awesomplete-selectcomplete", () => {
			this.$input.val('').focus();
		});		
		// used as an internal model to store values
		this.rows = [];

		this.$input_area.on('click', (e) => {
			if (e.target === this.$input_area.get(0)) {
				this.$input.focus();
			}
		});

		this.$input_area.on('click', '.btn-remove', (e) => {
			const $target = $(e.currentTarget);
			const $value = $target.closest('.tb-selected-value');

			const value = decodeURIComponent($value.data().value);
			this.rows = this.rows.filter(row => row !== value);

			this.parse_validate_and_set_in_model('');
		});
		this.$input_area.on('click', '.btn-link-to-form', (e) => {
			const $target = $(e.currentTarget);
			const $value = $target.closest('.tb-selected-value');

			const value = decodeURIComponent($value.data().value);
			frappe.set_route('Form', this.df.options, value);
		});
		this.$input.on('keydown', e => {
			// if backspace key pressed on empty input, delete last value
			if (e.keyCode == frappe.ui.keyCode.BACKSPACE && e.target.value === '') {
				this.rows = this.rows.slice(0, this.rows.length - 1);
				this.parse_validate_and_set_in_model('');
			}
		});
	},
	setup_buttons() {
		this.$input_area.find('.link-btn').remove();
	},

	parse(value) {
		if (value) {
			this.rows.push(value);
		}
		return this.rows.join(",");
	},

	validate(value) {
		if (value === "") return;
		if (typeof value === "string") value = value.split(",")

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

		return rows.join(",");
	},
	
	set_formatted_input(value) {
		if (typeof value === "string") value = value.split(",")
		this.rows = value || [];
		this.set_pill_html(this.rows);
	},
	set_pill_html(values) {
		const html = values
			.map(value => this.get_pill_html(value))
			.join('');

		this.$input_area.find('.tb-selected-value').remove();
		this.$input_area.prepend(html);
	},
	get_pill_html(value) {
		const encoded_value = encodeURIComponent(value);
		return `<div class="btn-group tb-selected-value" data-value="${encoded_value}">
			<button class="btn btn-default btn-xs btn-link-to-form">${__(value)}</button>
			<button class="btn btn-default btn-xs btn-remove">
				<i class="fa fa-remove text-muted"></i>
			</button>
		</div>`;
	},

	get_value() {
		return this.rows;
	},

	get_values() {
		return this.rows;
	},

	get_data() {
		let data;
		if(this.df.get_data) {
			data = this.df.get_data();
			if (data && data.then) {
				data.then((r) => {
					this.set_data(r);
				});
				data = this.get_value();
			} else {
				this.set_data(data);
			}
		} else {
			data = this._super();
		}
		const values = this.get_values() || [];

		// return values which are not already selected
		if (data) data.filter(d => !values.includes(d));
		return data;
	}
});