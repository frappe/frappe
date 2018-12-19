frappe.ui.form.ControlTableMultiSelect = frappe.ui.form.ControlLink.extend({
	make_input() {
        this.with_link_btn = true;
        this._super();

        this.$input_area.addClass('form-control table-multiselect');
        this.$input.removeClass('form-control');

        this.$input.on("awesomplete-selectcomplete", () => {
            this.$input.val('');
        });

        this.$input_area.on('click', '.btn-remove', (e) => {
            const $target = $(e.currentTarget);
            const $pill = $target.closest('.tb-selected-value');
            $pill.remove();
            this.parse_validate_and_set_in_model('');
        });
	},
    get_options() {
		return (this.get_link_field() || {}).options;
    },
    get_link_field() {
        const meta = frappe.get_meta(this.df.options);
        return meta.fields.find(df => df.fieldtype === 'Link');
    },
    setup_buttons() {
        this.$input_area.find('.link-btn').remove();
    },
    parse(value) {
        const values = Array.from(this.$input_area
            .find('.tb-selected-value'))
            .map((target) => {
                return decodeURIComponent($(target).data().value);
            });

        values.push(value);

        const link_field = this.get_link_field();
        return values.map(value => {
            return {
                [link_field.fieldname]: value
            };
        });
    },
    validate(value) {
		// validate the value just entered
		if (this.df.ignore_link_validation) {
			return value;
        }

        const link_field = this.get_link_field();
        if (value.length === 0) {
            return value;
        }

        const all_rows_except_last = value.slice(0, value.length - 1);
        const last_row = value[value.length - 1]

        // validate the last value entered
        const link_value = last_row[link_field.fieldname];

        // falsy value
        if (!link_value) {
            return all_rows_except_last;
        }

        // duplicate value
        if (all_rows_except_last.map(row => row[link_field.fieldname]).includes(link_value)) {
            return all_rows_except_last;
        }

		const validate_promise = this.validate_link_and_fetch(this.df, this.get_options(),
            this.docname, link_value);

        return validate_promise.then(validated_value => {
            if (validated_value === link_value) {
                return value
            } else {
                value.pop();
                return value;
            }
        })
	},
    set_formatted_input(value) {
        const docs = value || [];
        const link_field = this.get_link_field();
        const values = docs.map(row => row[link_field.fieldname]);
        this.set_pill_html(values)
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
            <button class="btn btn-default btn-xs">${__(value)}</button>
            <button class="btn btn-default btn-xs btn-remove">
                <i class="fa fa-remove text-muted"></i>
            </button>
        </div>`
    }
});
