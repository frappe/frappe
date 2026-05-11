import Awesomplete from "awesomplete";

frappe.ui.form.ControlMultiSelect = class ControlMultiSelect extends (
	frappe.ui.form.ControlAutocomplete
) {
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

			replace: function (text) {
				const before = this.input.value.match(/^.+,\s*|/)[0];
				this.input.value = before + text + ", ";
			},
		});
	}

	get_value() {
		let data = super.get_value();
		let options = this.get_parsed_options();

		// find value of label from option list and return actual value string
		if (options && options.length && options[0].label != undefined) {
			data = data.split(",").map((op) => op.trim());
			data = data
				.map((val) => {
					let option = options.find((op) => op.label === val);
					return option ? option.value : null;
				})
				.filter((n) => n != null)
				.join(", ");
		}
		return data;
	}

	set_formatted_input(value) {
		if (!value) return;
		let options = this.get_parsed_options();

		// find label of value from option list and set from it as input
		if (options && options.length && options[0].label != undefined) {
			value = value
				.split(",")
				.map((d) => d.trim())
				.map((val) => {
					let option = options.find((op) => op.value === val);
					return option ? option.label : val;
				})
				.filter((n) => n != null)
				.join(", ");
		}
		super.set_formatted_input(value);
	}

	get_parsed_options() {
		let options = this.df.options;
		if (typeof options === "string") {
			options = options.split("\n").map((option) => {
				return { label: __(option), value: option };
			});
		}
		return options;
	}

	get_values() {
		const value = this.get_value() || "";
		return value.split(/\s*,\s*/).filter((d) => d);
	}

	get_data() {
		let data;
		if (this.df.get_data) {
			data = this.df.get_data();
			if (data) this.set_data(data);
		} else {
			data = super.get_data();
		}
		const values = this.get_values() || [];

		// return values which are not already selected
		if (data) data.filter((d) => !values.includes(d));
		return data;
	}

	validate(value) {
		if (this.df.ignore_validation) {
			return value || "";
		}

		let valid_values = this.awesomplete._list.map((d) => d.value);

		if (!valid_values.length) {
			return value;
		}

		// remove last comma and convert into array
		let value_arr = value.replace(/,\s*$/, "").split(",");
		let include_all_values = value_arr.every((val) => valid_values.includes(val));

		if (include_all_values) {
			return value;
		} else {
			return "";
		}
	}
};
