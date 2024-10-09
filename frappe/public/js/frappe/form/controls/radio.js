frappe.ui.form.ControlRadio = class ControlRadio extends frappe.ui.form.ControlData {
    static trigger_change_on_input_event = false;

    make_input() {
        super.make_input();
        this.$input.addClass("radio-group");
        this.set_options();
    }

    set_options(value) {
        let options = this.df.options || [];
        if (typeof options === "string") {
            options = options.split("\n");
        }


        this.$wrapper.find(".radio-group").remove();

        const radioGroup = $('<div class="radio-group"></div>');

        options.forEach((option) => {
            const value = option.trim();
            const radioInput = `
                <div class="form-check flex align-items-baseline mb-2">
                    <input type="radio" class="form-check-input me-2" name="${this.df.fieldname}" value="${value}" id="${value}" ${this.read_only ? "disabled" : ""}>
                    <label class="form-check-label" for="${value}" style="margin-bottom: 0; display: flex; align-items: center;">${value}</label>
                </div>`;
            radioGroup.append(radioInput);
        });

        if (this.df.allow_others) {
            const othersRadio = `
                <div class="form-check d-flex align-items-baseline w-100 mb-2">
                    <input type="radio" class="form-check-input me-2" name="${this.df.fieldname}" value="others" id="others" ${this.read_only ? "disabled" : ""}>
                    <label class="form-check-label" for="others">Others</label>
                    <input type="text" class="form-control others-text-input ml-2" placeholder="Please specify..." style="display:none;" />
                </div>`;
            radioGroup.append(othersRadio);
        }

        this.$wrapper.find('.form-group').append(radioGroup);

        // Bind change event
        this.bind_change_event();
    }


    bind_change_event() {
        this.$wrapper.find('input[type="radio"]').on('change', (event) => {
            const value = $(event.target).val();

            if (value === "others") {
                this.$wrapper.find(".others-text-input").show();
            } else {
                this.$wrapper.find(".others-text-input").hide();
                this.set_model_value(value);
            }
        });

        // Bind blur event to "Others" text input
        this.$wrapper.find(".others-text-input").on('blur', () => {
            const othersValue = this.$wrapper.find(".others-text-input").val().trim();
            this.set_model_value(othersValue);
        });
    }

    set_formatted_input(value) {
        if (value == null) value = "";
        this.set_options(value);

        // Check if the value is not in the options
        const options = this.df.options ? this.df.options.split("\n").map(opt => opt.trim()) : [];
        if (!options.includes(value) && value) {
            this.$wrapper.find('input[type="radio"][value="others"]').prop('checked', true);
            this.$wrapper.find(".others-text-input").show();
            this.$wrapper.find(".others-text-input").val(value);
        } else {
            this.$wrapper.find(`input[type='radio'][value='${value}']`).prop('checked', true);
            this.$wrapper.find(".others-text-input").hide();
        }
    }

    get_value() {
        const checkedRadio = this.$wrapper.find("input[type='radio']:checked");
        if (checkedRadio.length > 0) {
            const value = checkedRadio.val();
            if (value === "others") {
                return this.$wrapper.find(".others-text-input").val();
            }
            return value;
        }
        return null;
    }

    set_value(value) {
        if (value === "others") {
            this.$wrapper.find("input[type='radio'][value='others']").prop("checked", true);
            this.$wrapper.find(".others-text-input").show();
        } else {
            this.$wrapper.find(`input[type='radio'][value='${value}']`).prop("checked", true);
            this.$wrapper.find(".others-text-input").hide();
        }
    }
};