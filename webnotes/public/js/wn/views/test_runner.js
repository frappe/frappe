// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.standard_pages["test-runner"] = function() {
	var wrapper = wn.container.add_page('test-runner');

	wn.ui.make_app_page({
		parent: wrapper,
		single_column: true,
		title: wn._("Test Runner")
	});
	
	$("<div id='qunit'></div>").appendTo($(wrapper).find(".layout-main"));

	var route = wn.get_route();
	if(route.length < 2) {
		msgprint("To run a test add the module name in the route after 'test-runner/'. \
			For example, #test-runner/lib/js/wn/test_app.js");
		return;
	}

	wn.require("assets/webnotes/js/lib/jquery/qunit.js");
	wn.require("assets/webnotes/js/lib/jquery/qunit.css");
	
	QUnit.load();

	wn.require(route.splice(1).join("/"));
}