frappe.ui.form.ControlAttachImage = class ControlAttachImage extends frappe.ui.form.ControlAttach {
	make_input() {
		super.make_input();

		let $file_link = this.$value.find(".attached-file-link");
		$file_link.popover({
			trigger: "hover",
			placement: "top",
			content: () => {
				return `<div>
					<img src="${this.get_value()}"
						width="150px"
						style="object-fit: contain;"
					/>
				</div>`;
			},
			html: true,
		});
	}
	set_upload_options() {
		super.set_upload_options();
		this.upload_options.restrictions.allowed_file_types = ["image/*"];
	}
};
