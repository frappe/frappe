frappe.ui.form.ControlBarcode = frappe.ui.form.ControlData.extend({
	make_wrapper() {
		// Create the elements
		this._super();
		this.barcode_area = $(`<div class="barcode-wrapper border"><svg height=80></svg></div>`)
			.appendTo(this.$wrapper.find('.control-input-wrapper'));
	},

	parse(value) {
		// Parse raw value
		return this.get_barcode_html(value, 2);
	},

	set_formatted_input(value) {
		// Set values to display
		const svg = value;
		const barcode_value = $(svg).attr('data-barcode-value');
		this.$input.val(barcode_value);
		this.barcode_area.html(svg);
	},

	get_barcode_html(value, width) {
		// Get svg
		const svg = this.barcode_area.find('svg')[0];
		JsBarcode(svg, value, {
			background:'#f5f7fa',
			width: width,
			height: 40
		});
		$(svg).attr('data-barcode-value', value);
		return this.barcode_area.html();
	}
});
