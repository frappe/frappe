frappe.ui.form.ControlHTML = class ControlHTML extends frappe.ui.form.Control {
	make() {
		super.make();
		this.disp_area = this.wrapper;
	}
	refresh_input() {
		var content = this.get_content();
		if (content) this.$wrapper.html(content);
	}
	get_content() {
		var content = this.df.options || "";
		content = __(content);
		try {
			return frappe.render(content, this);
		} catch (e) {
			return content;
		}
	}
	html(html) {
		this.$wrapper.html(html || this.get_content());
	}
	set_value(html) {
		if (html.appendTo) {
			// jquery object
			html.appendTo(this.$wrapper.empty());
		} else {
			// html
			this.df.options = html;
			this.html(html);
		}
		return Promise.resolve();
	}
};
