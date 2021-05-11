frappe.ui.form.ControlMarkdownEditor = class ControlMarkdownEditor extends frappe.ui.form.ControlCode {
	static editor_class = 'markdown'
	make_ace_editor() {
		super.make_ace_editor();

		this.ace_editor_target.wrap(`<div class="${this.editor_class}-container">`);
		this.markdown_container = this.$input_wrapper.find(`.${this.constructor.editor_class}-container`);

		this.editor.getSession().setUseWrapMode(true);

		this.showing_preview = false;
		this.preview_toggle_btn = $(`<button class="btn btn-default btn-xs ${this.editor_class}-toggle">${__('Preview')}</button>`)
			.click(e => {
				if (!this.showing_preview) {
					this.update_preview();
				}

				const $btn = $(e.target);
				this.markdown_preview.toggle(!this.showing_preview);
				this.ace_editor_target.toggle(this.showing_preview);

				this.showing_preview = !this.showing_preview;

				$btn.text(this.showing_preview ? __('Edit') : __('Preview'));
			});
		this.markdown_container.prepend(this.preview_toggle_btn);

		this.markdown_preview = $(`<div class="${this.editor_class}-preview border rounded">`).hide();
		this.markdown_container.append(this.markdown_preview);
	}

	set_language() {
		this.df.options = 'Markdown';
		super.set_language();
	}

	update_preview() {
		const value = this.get_value() || "";
		this.markdown_preview.html(frappe.markdown(value));
	}

	set_formatted_input(value) {
		super.set_formatted_input(value)
			.then(() => {
				this.update_preview();
			});
	}

	set_disp_area(value) {
		this.disp_area && $(this.disp_area).text(value);
	}
};
