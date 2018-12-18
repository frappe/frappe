frappe.ui.form.ControlHTMLEditor = frappe.ui.form.ControlCode.extend({
	make_input() {
		this._super();
		this.$input.height(150);
		this.make_preview_container();
	},

	make_preview_container() {
		this.html_preview_container = $('<div>').appendTo(this.input_area).addClass('html-preview-container');
		this.preview_label = $('<div>').appendTo(this.html_preview_container).addClass('html-preview-label');
		this.html_preview_area = $('<div>').appendTo(this.html_preview_container).addClass('html-preview-area');
		this.$input.on('change keyup paste', frappe.utils.debounce(() => {
			this.build_preview();
		}, 300));
	},

	set_formatted_input(value) {
		this._super(value);
		this.build_preview();
	},

	build_preview() {
		if (this.get_value() == '') {
			this.preview_label.text(__('No Preview available'));
			this.html_preview_area.hide();
		} else {
			this.preview_label.text(__('Preview'));
			this.html_preview_area.show();
			this.html_preview_area.html(this.get_value());
		}
	}
});
