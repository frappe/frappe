frappe.ui.form.ControlJSON = class ControlCode extends frappe.ui.form.ControlCode {
	set_language() {
		this.editor.session.setMode("ace/mode/json");
		this.editor.setKeyboardHandler("ace/keyboard/vscode");
	}

	get_placeholder_text() {
		const base_placeholder = super.get_placeholder_text();
		if (!base_placeholder) {
			return base_placeholder;
		}
		try {
			const parsed = JSON.parse(base_placeholder);
			return JSON.stringify(parsed, null, 2);
		} catch (error) {
			return base_placeholder;
		}
	}
};
