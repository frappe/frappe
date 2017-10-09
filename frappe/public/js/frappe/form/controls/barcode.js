frappe.ui.form.ControlBarcode = frappe.ui.form.ControlData.extend({
	make_wrapper() {
		this._super();
		this.$wrapper.find('.control-input').css({'display': 'flex'});
		// this.cam_buttom = $(`<button class="cam-button btn btn-sm btn-default text-muted" style="
		// 	margin-left: 5px;
		// "><i class="octicon octicon-device-camera"></i></button>`).appendTo(this.$wrapper.find('.control-input'));
		this.barcode_area = $(`<div class="barcode-wrapper like-disabled-input"
		"><svg id="barcode"></svg></div>`).appendTo(this.$wrapper.find('.control-input-wrapper'));
	},

	validate(value) {
		return this.render_barcode(value, 2);
	},

	render_barcode(value, width) {
		this.numeric_val = value;
		JsBarcode("#barcode", value, {
			format: "CODE128",
			background:'#f5f7fa',
			width: width,
			height: 40
		});
		let html = this.barcode_area.html();
		this.set_value(html);
		return html;
	}

});
