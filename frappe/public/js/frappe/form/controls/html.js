frappe.ui.form.ControlHTML = frappe.ui.form.Control.extend({
	make: function() {
		this._super();
		this.disp_area = this.wrapper;
	},
	refresh_input: function() {
		var content = this.get_content();
		if(content) this.$wrapper.html(content);
	},
	get_content: function() {
		var content = this.df.options || "";
		try {
			return frappe.render(content, this);
		} catch (e) {
			return content;
		}
	},
	html: function(html) {
		this.$wrapper.html(html || this.get_content());
	},
	set_value: function(html) {
		if(html.appendTo) {
			// jquery object
			html.appendTo(this.$wrapper.empty());
		} else {
			// html
			this.df.options = html;
			this.html(html);
		}
	}
});
