frappe.ui.form.ControlAttachImage = frappe.ui.form.ControlAttach.extend({
	make_input() {
		this._super();

		let $file_link = this.$value.find('.attached-file-link');
		$file_link.popover({
			trigger: 'hover',
			placement: 'top',
			content: () => {
				return `<div>
					<img src="${this.get_value()}"
						width="150px"
						style="object-fit: contain;"
					/>
				</div>`;
			},
			html: true
		});
	},
	set_upload_options() {
		this._super();
		this.upload_options.restrictions = {};
		this.upload_options.restrictions.allowed_file_types = ['image/*'];
	}
});
