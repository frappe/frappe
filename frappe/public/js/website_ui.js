frappe.ui.Dialog = class Dialog extends frappe.ui.Dialog {
	make() {
		super.make();
		if (this.fields) {
			this.$wrapper.find(".section-body").addClass("w-100");
		}
	}
};
