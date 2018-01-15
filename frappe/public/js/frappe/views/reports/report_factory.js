// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.ReportFactory = frappe.views.Factory.extend({
	make: function(route) {
		const _route = ['List', route[1], 'Report'];

		if (route[2]) {
			// custom report
			_route.push(route[2]);
		}

		frappe.set_route(_route);
	}
});
