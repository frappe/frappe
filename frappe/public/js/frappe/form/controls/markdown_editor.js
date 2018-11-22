frappe.ui.form.ControlMarkdownEditor = frappe.ui.form.ControlCode.extend({
	make_input() {
		this._super();
		this.$input.height(300);
		this.text_area = this.$input.first();
		this.showing_preview = false;

		this.make_preview_container();
		this.make_preview_button();
	},

	set_disp_area(value) {
		value = value || "";
		this.value = frappe.markdown(value);
		this._super();
	},

	set_formatted_input(value) {
		this._super(value);
		this.build_preview();
	},

	make_preview_button() {
		this.switch_button = $(`<button class="btn btn-default btn-add btn-xs"></button>`).appendTo(this.input_area);
		this.switch_button.html(__("Show Preview"));

		this.switch_button.click( () => {
			this.html_preview_area.toggle();
			this.text_area.toggle();
			this.showing_preview = !this.showing_preview;
			if (this.showing_preview) {
				this.switch_button.html(__("Show Markdown"));
			} else {
				this.switch_button.html(__("Show Preview"));
			}
		});
	},

	make_preview_container() {
		this.html_preview_container = $('<div>').appendTo(this.input_area).addClass('html-preview-container');
		this.html_preview_area = $('<div>').appendTo(this.html_preview_container).addClass('html-preview-area');
		this.html_preview_area.hide();

		this.text_area.on('change keyup paste', frappe.utils.debounce(() => {
			this.build_preview();
		}, 300));
	},

	build_preview() {
		var value = this.get_value() || "";
		this.html_preview_area.html(frappe.markdown(value));
	}
});
