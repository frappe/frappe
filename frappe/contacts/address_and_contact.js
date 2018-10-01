// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on(cur_frm.doctype, {
	get_last_doc: function() {
		const reverse_routes = frappe.route_history.reverse();
		const last_route = reverse_routes.find(route => {
			return route[0] === 'Form' && route[1] !== cur_frm.doctype
		})
		let doctype = last_route && last_route[1];
		let docname = last_route && last_route[2];

		if (last_route && last_route.length > 3)
			docname = last_route.slice(2).join("/");

		return {
			doctype,
			docname
		}
	}
});