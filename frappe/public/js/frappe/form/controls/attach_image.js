frappe.ui.form.ControlAttachImage = class ControlAttachImage extends frappe.ui.form.ControlAttach {
	make_input() {
		super.make_input();

		frappe.ui.hover_card(this.$value.find(".attached-file-link"), {
			open_delay: 0,
			close_delay: 0,
			content: () =>
				$("<img>", { src: this.get_value(), width: "150px" }).css(
					"object-fit",
					"contain"
				)[0],
		});
	}
	set_upload_options() {
		super.set_upload_options();
		this.upload_options.restrictions.allowed_file_types = [
			"image/jpeg",
			"image/png",
			"image/gif",
			"image/webp",
			"image/svg+xml",
			"image/avif",
			"image/bmp",
			"image/x-icon",
		];
	}
};
