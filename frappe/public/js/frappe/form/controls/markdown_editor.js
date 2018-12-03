frappe.ui.form.ControlMarkdownEditor = frappe.ui.form.ControlCode.extend({
	editor_class: 'markdown',
	make_ace_editor() {
		this._super();

		this.ace_editor_target.wrap(`<div class="${this.editor_class}-container">`);
		this.markdown_container = this.$input_wrapper.find(`.${this.editor_class}-container`);

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
	},

	set_language() {
		this.df.options = 'Markdown';
		this._super();
	},

	update_preview() {
		const value = this.get_value() || "";
		this.markdown_preview.html(frappe.markdown(value));
	}
});
