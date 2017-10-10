frappe.ui.form.ControlBarcode = frappe.ui.form.ControlData.extend({
	make_wrapper() {
		// Create the elements
		this._super();
		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');
		this.barcode_area = $(`<div class="barcode-wrapper border"><svg height=80></svg></div>`)
			.appendTo($input_wrapper);
	},

	parse(value) {
		// Parse raw value
		return this.get_barcode_html(value);
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
		JsBarcode(svg, value, {height: 40});
		$(svg).attr('data-barcode-value', value);
		return this.barcode_area.html();
	}
});
