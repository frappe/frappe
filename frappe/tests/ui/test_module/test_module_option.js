QUnit.module('views');

QUnit.test("Test option click [Module view]", function(assert) {
	assert.expect(4);
	let done = assert.async();

	frappe.run_serially([

		//click Document Share Report in Permissions section [Report]
		() => frappe.set_route("modules", "Setup"),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait('a.small:contains("Document Share Report")', 0),
		() => assert.deepEqual(frappe.get_route(), ["Report", "DocShare", "Document Share Report"], "First click test."),

		//click Print Setting in Printing section [Form]
		() => frappe.set_route("modules", "Setup"),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait('a.small:contains("Print Setting")', 0),
		() => assert.deepEqual(frappe.get_route(), ["Form", "Print Settings"], "Second click test."),

		//click Workflow Action in Workflow section [List]
		() => frappe.set_route("modules", "Setup"),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait('a.small:contains(" Workflow Action ")', 0),
		() => assert.deepEqual(frappe.get_route(), ["List", "Workflow Action", "List"], "Third click test."),

		//click Application Installer in Applications section
		() => frappe.set_route("modules", "Setup"),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait('a.small:contains("Application Installer")', 0),
		() => assert.deepEqual(frappe.get_route(), ["applications"], "Fourth click test."),

		() => done()
	]);
});