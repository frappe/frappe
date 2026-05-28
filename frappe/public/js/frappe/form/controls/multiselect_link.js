frappe.ui.form.ControlMultiSelectLink = class ControlMultiSelectLink extends (
	frappe.ui.form.ControlMultiSelect
) {
	make_input() {
		super.make_input();
		this.setup_paste_handler();
	}

	setup_paste_handler() {
		this.$input.on("paste", (e) => {
			const clipboard_data = (e.originalEvent || e).clipboardData;
			if (!clipboard_data) return;

			const pasted = clipboard_data.getData("text");
			if (!pasted) return;

			// Handle Excel paste (newline/tab separated values)
			if (!pasted.includes("\n") && !pasted.includes("\t")) return;

			e.preventDefault();

			const new_values = pasted
				.split(/[\n\t\r]+/)
				.map((v) => v.trim())
				.filter(Boolean);

			const existing = this.get_values();
			const merged = [...existing];
			for (const v of new_values) {
				if (!merged.includes(v)) {
					merged.push(v);
				}
			}

			this.$input.val(merged.join(", ") + (merged.length ? ", " : ""));
			this.$input.trigger("change");
		});
	}

	setup_awesomplete() {
		super.setup_awesomplete();

		// Override input handler to fetch async link data
		this.$input.off("input");
		this.$input.on(
			"input",
			frappe.utils.debounce(() => {
				const input = this.$input.val() || "";
				const txt = input.match(/[^,]*$/)[0].trim();
				this.fetch_and_set_data(txt);
			}, 300)
		);
	}

	fetch_and_set_data(txt) {
		if (!this.df.get_data) return;

		const result = this.df.get_data(txt);
		if (result && result.then) {
			result.then((data) => {
				if (!this.$input.is(":focus")) return;
				this.set_link_data(data);
			});
		} else if (result) {
			this.set_link_data(result);
		}
	}

	set_link_data(data) {
		// Read selected values from actual input text, not the model value
		// (model value lags behind after awesomplete selection)
		const selected = this.get_values();
		const filtered = (data || []).filter((d) => {
			const val = typeof d === "string" ? d : d.value;
			return !selected.includes(val);
		});
		this.set_data(filtered);
	}

	get_data() {
		if (this.df.get_data) {
			this.fetch_and_set_data("");
		}
		return this._data || [];
	}

	get_value() {
		if (this.$input) {
			const input_val = this.$input.val() || "";
			if (!input_val) return [];
			return input_val.split(/\s*,\s*/).filter(Boolean);
		}
		return this.value || [];
	}

	get_values() {
		return this.get_value();
	}

	set_formatted_input(value) {
		if (!this.$input) return;
		if (Array.isArray(value) && value.length) {
			this.$input.val(value.join(", ") + ", ");
		} else if (typeof value === "string" && value) {
			this.$input.val(value.endsWith(", ") ? value : value + ", ");
		} else {
			this.$input.val("");
		}
	}

	validate(value) {
		if (Array.isArray(value)) return value;
		if (typeof value === "string" && value) {
			return value.split(/\s*,\s*/).filter(Boolean);
		}
		return [];
	}
};
