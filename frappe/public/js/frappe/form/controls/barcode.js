frappe.ui.form.ControlBarcode = frappe.ui.form.ControlData.extend({
	make_input() {
		this._super();
	},

	make_wrapper() {
		this._super();
		this.$wrapper.find('.control-input').css({'display': 'flex'});
		// this.cam_buttom = $(`<button class="cam-button btn btn-sm btn-default text-muted" style="
		// 	margin-left: 5px;
		// "><i class="octicon octicon-device-camera"></i></button>`).appendTo(this.$wrapper.find('.control-input'));
		this.barcode_area = $(`<div class="barcode-wrapper like-disabled-input"
		"><svg id="barcode"></svg></div>`).appendTo(this.$wrapper.find('.control-input-wrapper'));
	},

	set_input(value) {
		this._super();
		this.render_barcode(value, 2);
	},

	render_barcode(value, width) {
		JsBarcode("#barcode", value, {
			format: "CODE128",
			background:'#f5f7fa',
			width: width,
			height: 40
		});
		this.barcode_svg = this.barcode_area.html();
	},

	// setup_cam(){
	// 	this.setup_cam_dialog();
	// 	this.cam_buttom.on('click', () => {
	// 		this.cam_dialog.show();
	// 	});
	// },

	// setup_cam_dialog() {
	// 	this.cam_dialog = new frappe.ui.Dialog({
	// 		title: __(this.df.label || __("Capture"))
	// 	});
	// },

	// get_cam_data() {
	// 	//
	// }
});
