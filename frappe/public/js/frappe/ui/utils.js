frappe.provide('frappe.ui');

frappe.ui.dom = {
	activate($parent, $child, common_class, active_class='active') {
		$parent.find(`.${common_class}.${active_class}`)
			.removeClass(active_class);
		$child.addClass(active_class);
	},
}