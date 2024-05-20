frappe.ui.form.ControlMarkdownEditor = class ControlMarkdownEditor extends (
	frappe.ui.form.ControlCode
) {
	static editor_class = "markdown";
	make_ace_editor() {
		super.make_ace_editor();
		if (this.markdown_container) return;

		let editor_class = this.constructor.editor_class;
		this.ace_editor_target.wrap(`<div class="${editor_class}-container">`);
		this.markdown_container = this.$input_wrapper?.find(`.${editor_class}-container`);

		this.editor.getSession().setUseWrapMode(true);

		this.showing_preview = false;
		this.preview_toggle_btn = $(
			`<button class="btn btn-default btn-xs ${editor_class}-toggle">${__(
				"Preview"
			)}</button>`
		).click((e) => {
			if (!this.showing_preview) {
				this.update_preview();
			}

			const $btn = $(e.target);
			this.markdown_preview.toggle(!this.showing_preview);
			this.ace_editor_target.toggle(this.showing_preview);

			this.showing_preview = !this.showing_preview;

			$btn.text(this.showing_preview ? __("Edit") : __("Preview"));
		});
		this.markdown_container?.prepend(this.preview_toggle_btn);

		this.markdown_preview = $(`<div class="${editor_class}-preview border rounded">`).hide();
		this.markdown_container?.append(this.markdown_preview);

		this.setup_image_drop();
	}

	set_language() {
		if (!this.df.options) {
			this.df.options = "Markdown";
		}
		super.set_language();
	}

	update_preview() {
		if (!this.markdown_preview) return;
		const value = this.get_value() || "";
		this.markdown_preview.html(frappe.markdown(value));
	}

	set_formatted_input(value) {
		super.set_formatted_input(value).then(() => {
			this.update_preview();
		});
	}

	set_disp_area(value) {
		this.disp_area && $(this.disp_area).text(value);
	}

	setup_image_drop() {
		this.ace_editor_target.on("drop", (e) => {
			e.stopPropagation();
			e.preventDefault();
			let { dataTransfer } = e.originalEvent;
			if (!dataTransfer?.files?.length) {
				return;
			}
			let files = dataTransfer.files;
			if (!files[0].type.includes("image")) {
				frappe.show_alert({
					message: __("You can only insert images in Markdown fields", [files[0].name]),
					indicator: "orange",
				});
				return;
			}

			new frappe.ui.FileUploader({
				dialog_title: __("Insert Image in Markdown"),
				doctype: this.doctype,
				docname: this.docname,
				frm: this.frm,
				files,
				folder: "Home/Attachments",
				allow_multiple: false,
				restrictions: {
					allowed_file_types: ["image/*"],
				},
				on_success: (file_doc) => {
					if (this.frm && !this.frm.is_new()) {
						this.frm.attachments.attachment_uploaded(file_doc);
					}
					this.editor.session.insert(
						this.editor.getCursorPosition(),
						`![](${encodeURI(file_doc.file_url)})`
					);
				},
			});
		});
	}
};
