// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.standard_pages["test-runner"] = function() {
	var wrapper = frappe.container.add_page('test-runner');

	frappe.ui.make_app_page({
		parent: wrapper,
		single_column: true,
		title: __("Test Runner")
	});

	$("<div id='qunit'></div>").appendTo($(wrapper).find(".layout-main"));

	var route = frappe.get_route();
	if(route.length < 2) {
		msgprint(__("To run a test add the module name in the route after '{0}'. For example, {1}", ['test-runner/', '#test-runner/lib/js/frappe/test_app.js']));
		return;
	}

	frappe.require("assets/frappe/js/lib/jquery/qunit.js");
	frappe.require("assets/frappe/js/lib/jquery/qunit.css");

	QUnit.load();

	frappe.require(route.splice(1).join("/"));
}
