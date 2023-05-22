import JsBarcode from "jsbarcode";

frappe.ui.form.ControlBarcode = class ControlBarcode extends frappe.ui.form.ControlData {
	make_wrapper() {
		// Create the elements for barcode area
		super.make_wrapper();

		this.default_svg = "<svg height=80></svg>";
		let $input_wrapper = this.$wrapper.find(".control-input-wrapper");
		this.barcode_area = $(`<div class="barcode-wrapper">${this.default_svg}</div>`);
		this.barcode_area.appendTo($input_wrapper);
	}

	parse(value) {
		// Parse raw value
		if (value) {
			if (value.startsWith("<svg")) {
				return value;
			}
			return this.get_barcode_html(value);
		}
		return "";
	}

	set_formatted_input(value) {
		// Set values to display
		let svg = value;
		let barcode_value = "";

		this.set_empty_description();
		if (value && value.startsWith("<svg")) {
			barcode_value = $(svg).attr("data-barcode-value");
		}

		if (!barcode_value && this.doc) {
			svg = this.get_barcode_html(value);
			this.doc[this.df.fieldname] = svg;
		}

		this.$input.val(barcode_value || value);
		this.barcode_area.html(svg || this.default_svg);
	}

	get_barcode_html(value) {
		if (value) {
			// Get svg
			const svg = this.barcode_area.find("svg")[0];
			try {
				JsBarcode(svg, value, this.get_options(value));
				$(svg).attr("data-barcode-value", value);
				$(svg).attr("width", "100%");
				return this.barcode_area.html();
			} catch (e) {
				this.set_description(`Invalid Barcode: ${String(e)}`);
			}
		}
	}

	get_options(value) {
		// get JsBarcode options
		let options = {};
		options.fontSize = "16";
		options.width = "3";
		options.height = "50";

		if (frappe.utils.is_json(this.df.options)) {
			options = JSON.parse(this.df.options);
			if (options.format && options.format === "EAN") {
				options.format = value.length == 8 ? "EAN8" : "EAN13";
			}

			if (options.valueField) {
				// Set companion field value
				this.frm && this.frm.set_value(options.valueField, value);
			}
		}
		return options;
	}
};
