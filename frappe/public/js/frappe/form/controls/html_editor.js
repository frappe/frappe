frappe.ui.form.ControlHTMLEditor = frappe.ui.form.ControlMarkdownEditor.extend({
	editor_class: 'html',
	set_language() {
		this.df.options = 'HTML';
		this._super();
	},
	update_preview() {
		let value = this.get_value() || '';
		value = frappe.dom.remove_script_and_style(value);
		this.markdown_preview.html(value);
	}
});
