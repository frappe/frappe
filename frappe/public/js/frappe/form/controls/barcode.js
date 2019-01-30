import JsBarcode from "jsbarcode";

frappe.ui.form.ControlBarcode = frappe.ui.form.ControlData.extend({
	make_wrapper() {
		// Create the elements for barcode area
		this._super();

		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');
		this.barcode_area = $(`<div class="barcode-wrapper border"><svg height=80></svg></div>`);
		this.barcode_area.appendTo($input_wrapper);
	},

	parse(value) {
		// Parse raw value
		return value ? this.get_barcode_html(value) : "";
	},

	set_formatted_input(value) {
		// Set values to display
		const svg = value;
		const barcode_value = $(svg).attr('data-barcode-value');

		this.$input.val(barcode_value);
		this.barcode_area.html(svg);
	},

	get_barcode_html(value) {
		// Get svg
		const svg = this.barcode_area.find('svg')[0];
		JsBarcode(svg, value, this.get_options(value));
		$(svg).attr('data-barcode-value', value);
		return this.barcode_area.html();
	},

	get_options(value) {
		// get JsBarcode options
		let options = JSON.parse('{ "height" : 40 }');
		if (this.isValidJson(this.df.options)) {
			options = JSON.parse(this.df.options);
			if (options.format && options.format === "EAN") {
				options.format = value.length == 8 ? "EAN8" : "EAN13";
			}

			if (options.valueField) {
				// Set companion field value
				this.frm.set_value(options.valueField, value);
			}
		}
		return options;
	},

	isValidJson(jsonData) {
		try {
			JSON.parse(jsonData);
			return true;
		} catch (e) {
			return false;
		}
	}

});
