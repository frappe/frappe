frappe.ui.form.ControlDynamicLink = frappe.ui.form.ControlLink.extend({
	get_options: function() {
		if(this.df.get_options) {
			return this.df.get_options();
		}
		if (this.docname==null && cur_dialog) {
			//for dialog box
			return cur_dialog.get_value(this.df.options);
		}
		if (!cur_frm) {
			const selector = `input[data-fieldname="${this.df.options}"]`;
			let input = null;
			if (cur_list) {
				// for list page
				input = cur_list.wrapper.find(selector);
			}
			if (cur_page) {
				input = $(cur_page.page).find(selector);
			}
			if (input) {
				return input.val();
			}
		}
		var options = frappe.model.get_value(this.df.parent, this.docname, this.df.options);
		// if(!options) {
		// 	frappe.msgprint(__("Please set {0} first",
		// 		[frappe.meta.get_docfield(this.df.parent, this.df.options, this.docname).label]));
		// }
		return options;
	},
});
